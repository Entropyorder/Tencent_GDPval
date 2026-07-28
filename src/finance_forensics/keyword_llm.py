from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import time

from openai import BadRequestError, OpenAI

from .llm import extract_json_object
from .models import QueryKeywordsDraft


def normalize_keyword_payload(payload):
    values = payload.get("keywords", [])
    if not isinstance(values, list):
        values = [values]
    keywords = []
    seen = set()
    for value in values:
        keyword = str(value).strip()
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        keywords.append(keyword)
    return {"keywords": keywords[:8]}


class QueryKeywordClient:
    prompt_version = "query_keywords_v3"

    def __init__(self, settings):
        settings.validate_api()
        self.settings = settings
        prompt_dir = settings.prompt_path.parent
        self.system_prompt = (prompt_dir / "检索关键词提取.md").read_text(
            encoding="utf-8"
        )
        self.user_prompt_template = (
            prompt_dir / "检索关键词输入模板.md"
        ).read_text(encoding="utf-8")
        self.prompt_sha256 = hashlib.sha256(
            (self.system_prompt + "\0" + self.user_prompt_template).encode(
                "utf-8"
            )
        ).hexdigest()
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=180,
            max_retries=0,
        )

    def build_user_prompt(self, query):
        return self.user_prompt_template.format(
            schema=json.dumps(
                QueryKeywordsDraft.model_json_schema(), ensure_ascii=False
            ),
            query=query,
        )

    def extract(self, query, retries=3):
        user_prompt = self.build_user_prompt(query)
        use_response_format = True
        last_error = None
        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                kwargs = {
                    "model": self.settings.model,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": self.settings.keyword_temperature,
                    "max_tokens": self.settings.keyword_max_output_tokens,
                }
                if use_response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**kwargs)
                if response.choices[0].finish_reason == "length":
                    raise ValueError(
                        "model response was truncated; increase "
                        "KEYWORD_MAX_OUTPUT_TOKENS"
                    )
                payload = normalize_keyword_payload(
                    extract_json_object(response.choices[0].message.content)
                )
                return QueryKeywordsDraft.model_validate(payload)
            except BadRequestError as exc:
                if use_response_format:
                    use_response_format = False
                    attempt -= 1
                    continue
                last_error = exc
            except Exception as exc:
                last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(
            f"keyword extraction failed after {retries} attempts: {last_error}"
        )


def keyword_cache_identity(queries, client):
    digest = hashlib.sha256()
    for query in queries:
        digest.update(query.encode("utf-8"))
        digest.update(b"\0")
    return {
        "model": client.settings.model,
        "prompt_version": client.prompt_version,
        "prompt_sha256": getattr(client, "prompt_sha256", ""),
        "queries_sha256": digest.hexdigest(),
    }


def write_keyword_cache(path, identity, queries, results):
    payload = {
        "schema_version": "1.0",
        **identity,
        "query_count": len(queries),
        "items": [
            {
                "query_index": index,
                "query": queries[index - 1],
                "keywords": results[index],
            }
            for index in sorted(results)
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def load_or_extract_query_keywords(
    queries,
    client,
    cache_path,
    workers=8,
):
    if workers < 1:
        raise ValueError("keyword workers must be at least 1")
    cache_path = Path(cache_path)
    identity = keyword_cache_identity(queries, client)
    results = {}
    if cache_path.is_file():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if all(payload.get(key) == value for key, value in identity.items()):
            for item in payload.get("items", []):
                index = item.get("query_index")
                if (
                    isinstance(index, int)
                    and 1 <= index <= len(queries)
                    and item.get("query") == queries[index - 1]
                ):
                    draft = QueryKeywordsDraft.model_validate(
                        {"keywords": item.get("keywords", [])}
                    )
                    results[index] = draft.keywords

    pending = [
        index for index in range(1, len(queries) + 1) if index not in results
    ]
    if pending:
        print(
            f"[keywords] selected={len(queries)} cached={len(results)} "
            f"pending={len(pending)} workers={workers}",
            flush=True,
        )
        errors = {}
        with ThreadPoolExecutor(
            max_workers=min(workers, len(pending))
        ) as executor:
            futures = {
                executor.submit(client.extract, queries[index - 1]): index
                for index in pending
            }
            for completed, future in enumerate(as_completed(futures), start=1):
                index = futures[future]
                try:
                    results[index] = future.result().keywords
                    status = "success"
                except Exception as exc:
                    errors[index] = f"{type(exc).__name__}: {exc}"
                    status = "failed"
                write_keyword_cache(cache_path, identity, queries, results)
                print(
                    f"[keywords] {completed}/{len(pending)} "
                    f"status={status} query={index}",
                    flush=True,
                )
        if errors:
            details = "; ".join(
                f"query {index}: {error}"
                for index, error in sorted(errors.items())
            )
            raise RuntimeError(f"keyword extraction failed: {details}")

    print(
        f"[keywords] done queries={len(queries)} cache={cache_path}",
        flush=True,
    )
    return [results[index] for index in range(1, len(queries) + 1)]
