from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import time

from .extractors import (
    ExtractionError,
    ExtractionResult,
    SUPPORTED_EXTENSIONS,
    extract_document,
)
from .metadata import CollectorMetadata
from .models import (
    DocumentRecord,
    ExtractionDetails,
    ProcessingDetails,
    RenamingDetails,
    SourceDetails,
)
from .naming import normalize_filename, profile_to_record_fields


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def document_id_for_hash(sha256):
    return f"doc_{sha256[:16]}"


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def extraction_details(result, status="success"):
    return ExtractionDetails(
        status=status,
        method=result.method,
        characters=result.characters,
        total_units=result.total_units,
        units_read=result.units_read,
        truncated=result.truncated,
        encoding=result.encoding,
        warnings=result.warnings,
    )


class DocumentProcessor:
    def __init__(self, settings, llm_client, collector_metadata):
        self.settings = settings
        self.llm_client = llm_client
        self.collector_metadata = collector_metadata

    def process(self, path):
        path = Path(path).resolve()
        started = time.monotonic()
        digest = sha256_file(path)
        document_id = document_id_for_hash(digest)
        crawler = self.collector_metadata.for_file(path)
        source = SourceDetails(
            absolute_path=str(path),
            extension=path.suffix.lower(),
            size_bytes=path.stat().st_size,
            sha256=digest,
            crawler_url=crawler.get("url"),
            crawler_title=crawler.get("title"),
            crawler_query=crawler.get("query"),
            search_index=crawler.get("searchIndex"),
            search_index_one_based=crawler.get("searchIndexOneBased"),
            collected_at=crawler.get("collectedAt"),
        )

        extracted = None
        try:
            extracted = extract_document(path, self.settings.max_input_chars)
            context = {
                "document_id": document_id,
                "source_filename": path.name,
                "extension": path.suffix.lower(),
                "size_bytes": path.stat().st_size,
                "crawler": crawler,
                "extraction": {
                    "method": extracted.method,
                    "characters": extracted.characters,
                    "total_units": extracted.total_units,
                    "units_read": extracted.units_read,
                    "truncated": extracted.truncated,
                    "warnings": extracted.warnings,
                },
            }
            profile = self.llm_client.analyze(context, extracted.text)
            normalized_filename = normalize_filename(
                profile.suggested_filename, path, document_id, profile
            )
            record = DocumentRecord(
                document_id=document_id,
                source_filename=path.name,
                suggested_filename=normalized_filename,
                **profile_to_record_fields(profile),
                source=source,
                extraction=extraction_details(extracted),
                renaming=RenamingDetails(
                    llm_suggested_filename=profile.suggested_filename,
                    normalized_filename=normalized_filename,
                    applied=False,
                ),
                processing=ProcessingDetails(
                    status="success",
                    model=self.settings.model,
                    prompt_version=self.settings.prompt_version,
                    processed_at=now_iso(),
                    duration_seconds=round(time.monotonic() - started, 3),
                ),
            )
            return record
        except Exception as exc:
            extraction_failed = extracted is None
            warning = "本地文本抽取失败" if extraction_failed else "模型调用或结构校验失败"
            extraction = (
                ExtractionDetails(
                    status="failed",
                    method=path.suffix.lower().lstrip(".") or "unknown",
                    characters=0,
                    warnings=[str(exc)],
                )
                if extraction_failed
                else extraction_details(extracted)
            )
            return DocumentRecord(
                document_id=document_id,
                source_filename=path.name,
                needs_review=True,
                review_reasons=[warning],
                source=source,
                extraction=extraction,
                renaming=RenamingDetails(applied=False),
                processing=ProcessingDetails(
                    status="failed",
                    model=self.settings.model,
                    prompt_version=self.settings.prompt_version,
                    processed_at=now_iso(),
                    duration_seconds=round(time.monotonic() - started, 3),
                    error=f"{type(exc).__name__}: {exc}",
                ),
            )


def discover_files(input_dir):
    return sorted(
        path
        for path in Path(input_dir).iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_latest_checkpoint(path):
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
                source_path = record.get("source", {}).get("absolute_path")
                if source_path:
                    latest[source_path] = record
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid checkpoint JSON at line {line_number}: {exc}"
                ) from exc
    return latest


def append_checkpoint(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(record.model_dump_json(exclude_none=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def prune_none(value):
    if isinstance(value, dict):
        return {
            key: prune_none(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, list):
        return [prune_none(item) for item in value]
    return value


def finalize_checkpoint(checkpoint_path, output_path):
    latest = load_latest_checkpoint(checkpoint_path)
    records = sorted(
        (prune_none(record) for record in latest.values()),
        key=lambda item: (
            item.get("source_filename", ""),
            item.get("document_id", ""),
        ),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp = output_path.with_suffix(output_path.suffix + ".tmp")
    temp.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temp, output_path)
    return records


def run_batch(
    processor,
    files,
    checkpoint_path,
    output_path,
    workers=2,
    retry_failed=False,
):
    existing = load_latest_checkpoint(checkpoint_path)
    pending = []
    for path in files:
        previous = existing.get(str(Path(path).resolve()))
        if previous is None:
            pending.append(path)
        elif retry_failed and previous.get("processing", {}).get("status") == "failed":
            pending.append(path)

    print(
        f"[run] discovered={len(files)} existing={len(existing)} pending={len(pending)} "
        f"workers={workers}"
    )
    completed = 0
    success = 0
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(processor.process, path): path for path in pending}
        for future in as_completed(futures):
            record = future.result()
            append_checkpoint(checkpoint_path, record)
            completed += 1
            if record.processing.status == "success":
                success += 1
            else:
                failed += 1
            print(
                f"[run] {completed}/{len(pending)} status={record.processing.status} "
                f"file={record.source_filename}",
                flush=True,
            )

    records = finalize_checkpoint(checkpoint_path, output_path)
    print(
        f"[run] done new_success={success} new_failed={failed} "
        f"catalog_records={len(records)} output={output_path}"
    )
    return records


def inspect_file(path, max_chars):
    result = extract_document(path, max_chars)
    return {
        "path": str(Path(path).resolve()),
        "method": result.method,
        "characters": result.characters,
        "total_units": result.total_units,
        "units_read": result.units_read,
        "truncated": result.truncated,
        "encoding": result.encoding,
        "warnings": result.warnings,
        "preview": result.text[:1500],
    }
