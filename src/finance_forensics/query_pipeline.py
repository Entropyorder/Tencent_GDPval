from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

from .extractors import extract_document
from .models import QueryGenerationDetails, QueryRecord
from .pipeline import now_iso


def task_id_for_document(document_id, prompt_version="gdpval_query_v3"):
    return str(uuid5(NAMESPACE_URL, f"{document_id}:{prompt_version}"))


def load_catalog(path):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    return {record["source_filename"]: record for record in records}


def load_latest_query_checkpoint(path):
    latest = {}
    path = Path(path)
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                source_document_id = record.get("source_document_id")
                if source_document_id:
                    latest[source_document_id] = record
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid query checkpoint JSON at line {line_number}: {exc}"
                ) from exc
    return latest


def append_query_checkpoint(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(record.model_dump_json(exclude_none=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def finalize_query_checkpoint(checkpoint_path, output_path):
    latest = load_latest_query_checkpoint(checkpoint_path)
    records = sorted(
        latest.values(),
        key=lambda item: (item.get("source_filename", ""), item.get("task_id", "")),
    )
    queries = [
        {"query": record["query"]}
        for record in records
        if record.get("generation", {}).get("status") == "success"
        and record.get("query")
    ]
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temporary, output_path)
    return queries


class QueryProcessor:
    def __init__(self, settings, llm_client, catalog):
        self.settings = settings
        self.llm_client = llm_client
        self.catalog = catalog

    def process(self, path):
        path = Path(path).resolve()
        started = time.monotonic()
        profile = self.catalog[path.name]
        document_id = profile["document_id"]
        task_id = task_id_for_document(document_id, self.llm_client.prompt_version)
        try:
            forbidden_specific_terms = [
                path.name,
                *(
                    profile.get(key)
                    for key in (
                        "subject_name",
                        "company_name",
                        "security_code",
                        "reporting_period",
                        "publish_date",
                        "business_topic",
                        "industry",
                        "market",
                    )
                ),
            ]
            extracted = extract_document(path, self.settings.max_input_chars)
            context = {
                "forbidden_specific_terms": [
                    term for term in forbidden_specific_terms if term
                ],
                "document_type": profile.get("document_type") or "other",
                "variation_marker": task_id.replace("-", "")[-8:],
            }
            draft = self.llm_client.generate(context, extracted.text)
            return QueryRecord(
                task_id=task_id,
                query=draft.query,
                source_document_id=document_id,
                source_filename=path.name,
                generation=QueryGenerationDetails(
                    status="success",
                    model=self.settings.model,
                    prompt_version=self.llm_client.prompt_version,
                    processed_at=now_iso(),
                    duration_seconds=round(time.monotonic() - started, 3),
                ),
            )
        except Exception as exc:
            return QueryRecord(
                task_id=task_id,
                source_document_id=document_id,
                source_filename=path.name,
                generation=QueryGenerationDetails(
                    status="failed",
                    model=self.settings.model,
                    prompt_version=self.llm_client.prompt_version,
                    processed_at=now_iso(),
                    duration_seconds=round(time.monotonic() - started, 3),
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )


def run_query_batch(
    processor,
    files,
    checkpoint_path,
    output_path,
    workers=2,
    retry_failed=False,
):
    existing = load_latest_query_checkpoint(checkpoint_path)
    pending = []
    for path in files:
        document_id = processor.catalog[Path(path).name]["document_id"]
        previous = existing.get(document_id)
        if previous is None or (
            previous.get("generation", {}).get("status") == "success"
            and not previous.get("query")
        ):
            pending.append(path)
        elif retry_failed and previous.get("generation", {}).get("status") == "failed":
            pending.append(path)

    print(
        f"[queries] selected={len(files)} existing={len(existing)} "
        f"pending={len(pending)} workers={workers}"
    )
    success = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(processor.process, path): path for path in pending}
        for completed, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            append_query_checkpoint(checkpoint_path, record)
            if record.generation.status == "success":
                success += 1
            else:
                failed += 1
            print(
                f"[queries] {completed}/{len(pending)} "
                f"status={record.generation.status} file={record.source_filename}",
                flush=True,
            )

    queries = finalize_query_checkpoint(checkpoint_path, output_path)
    print(
        f"[queries] done new_success={success} new_failed={failed} "
        f"output_queries={len(queries)} output={output_path}"
    )
    return queries
