import json
import re
import time

from openai import BadRequestError, OpenAI

from .llm import extract_json_object
from .models import QueryDraft


def normalize_query_payload(payload):
    allowed = set(QueryDraft.model_fields)
    normalized = {key: value for key, value in payload.items() if key in allowed}
    normalized["query"] = str(normalized.get("query", "")).strip()
    return normalized


class GDPvalQueryClient:
    prompt_version = "gdpval_query_v3"

    def __init__(self, settings):
        settings.validate_api()
        self.settings = settings
        prompt_path = settings.prompt_path.parent / "通用查询生成.md"
        self.system_prompt = prompt_path.read_text(encoding="utf-8")
        self.user_prompt_template = (
            settings.prompt_path.parent / "通用查询输入模板.md"
        ).read_text(encoding="utf-8")
        self.client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout=180,
            max_retries=0,
        )

    def build_user_prompt(self, context, document_content=""):
        schema = QueryDraft.model_json_schema()
        public_context = {
            key: value
            for key, value in context.items()
            if key != "forbidden_specific_terms"
        }
        return self.user_prompt_template.format(
            schema=json.dumps(schema, ensure_ascii=False),
            context=json.dumps(public_context, ensure_ascii=False, indent=2),
            document_content=document_content[: self.settings.max_input_chars],
        )

    def generate(self, context, document_content, retries=3):
        user_prompt = self.build_user_prompt(context, document_content)
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
                    "temperature": self.settings.query_temperature,
                    "max_tokens": self.settings.query_max_output_tokens,
                }
                if use_response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self.client.chat.completions.create(**kwargs)
                if response.choices[0].finish_reason == "length":
                    raise ValueError(
                        "model response was truncated; increase QUERY_MAX_OUTPUT_TOKENS"
                    )
                payload = normalize_query_payload(
                    extract_json_object(response.choices[0].message.content)
                )
                if not payload["query"]:
                    raise ValueError("query must not be empty")
                draft = QueryDraft.model_validate(payload)
                forbidden_terms = context.get("forbidden_specific_terms", [])
                leaked = [
                    term for term in forbidden_terms
                    if len(term) >= 2 and term in draft.query
                ]
                meta_markers = (
                    "具体公司名称",
                    "具体机构名称",
                    "证券代码",
                    "报告编号",
                    "通用称谓",
                    "不得使用具体",
                    "避免使用具体",
                )
                if (
                    leaked
                    or re.search(r"\d", draft.query)
                    or any(marker in draft.query for marker in meta_markers)
                ):
                    details = ", ".join(leaked[:3]) or "Arabic numeral"
                    raise ValueError(f"query contains source-specific details: {details}")
                return draft
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
            f"query generation failed after {retries} attempts: {last_error}"
        )
