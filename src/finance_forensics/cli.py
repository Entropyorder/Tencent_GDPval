import argparse
from collections import Counter
import json
from pathlib import Path

from pydantic import TypeAdapter

from .config import (
    DEFAULT_COLLECTOR_JSON,
    DEFAULT_INPUT_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    Settings,
)
from .extractors import SUPPORTED_EXTENSIONS
from .keyword_llm import QueryKeywordClient, load_or_extract_query_keywords
from .llm import InfereraClient
from .metadata import CollectorMetadata
from .models import DocumentRecord
from .models import QueryDraft
from .pipeline import (
    DocumentProcessor,
    discover_files,
    inspect_file,
    run_batch,
)
from .query_llm import GDPvalQueryClient
from .query_pipeline import QueryProcessor, load_catalog, run_query_batch
from .retrieval import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_KEYWORD_WEIGHT,
    DEFAULT_SEMANTIC_WEIGHT,
    load_queries,
    retrieve_attachments,
)


DEFAULT_OUTPUT = OUTPUT_DIR / "catalog" / "document_catalog.json"
DEFAULT_CHECKPOINT = OUTPUT_DIR / "catalog" / "document_catalog.jsonl"
DEFAULT_QUERY_INPUT = DEFAULT_INPUT_DIR
DEFAULT_QUERY_OUTPUT = OUTPUT_DIR / "queries" / "gdpval_queries.json"
DEFAULT_QUERY_CHECKPOINT = OUTPUT_DIR / "queries" / "gdpval_queries.jsonl"


def add_source_arguments(parser):
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--collector-json", type=Path, default=DEFAULT_COLLECTOR_JSON
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="finance-forensics",
        description="Extract, summarize, and catalog finance documents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="List input file counts.")
    add_source_arguments(inventory)

    inspect = subparsers.add_parser(
        "inspect", help="Extract one local file without calling the LLM."
    )
    inspect.add_argument("file", type=Path)
    inspect.add_argument("--max-chars", type=int, default=5000)

    check_api = subparsers.add_parser(
        "check-api", help="Validate API/model/JSON using synthetic content."
    )
    check_api.add_argument("--show-result", action="store_true")

    schema = subparsers.add_parser("schema", help="Write the JSON Schema.")
    schema.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "schemas" / "document_record.schema.json",
    )

    run = subparsers.add_parser("run", help="Run explicit LLM processing.")
    add_source_arguments(run)
    run.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    run.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    run.add_argument("--workers", type=int, default=2)
    run.add_argument("--limit", type=int)
    run.add_argument("--retry-failed", action="store_true")

    query_schema = subparsers.add_parser(
        "query-schema", help="Write the GDPval-style query JSON Schema."
    )
    query_schema.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR / "schemas" / "query.schema.json",
    )

    generate_queries = subparsers.add_parser(
        "generate-queries",
        help="Generate GDPval-style professional tasks from cataloged files.",
    )
    generate_queries.add_argument("--input-dir", type=Path, default=DEFAULT_QUERY_INPUT)
    generate_queries.add_argument(
        "--catalog", type=Path, default=DEFAULT_OUTPUT
    )
    generate_queries.add_argument("--output", type=Path, default=DEFAULT_QUERY_OUTPUT)
    generate_queries.add_argument(
        "--checkpoint", type=Path, default=DEFAULT_QUERY_CHECKPOINT
    )
    generate_queries.add_argument(
        "--source-file",
        action="append",
        help="Generate only for this exact source filename; may be repeated.",
    )
    generate_queries.add_argument("--limit", type=int)
    generate_queries.add_argument("--workers", type=int, default=2)
    generate_queries.add_argument("--retry-failed", action="store_true")

    retrieve = subparsers.add_parser(
        "retrieve-attachments",
        help="Retrieve and copy the most relevant files for generated queries.",
    )
    retrieve.add_argument(
        "--queries",
        type=Path,
        default=OUTPUT_DIR / "queries" / "query_test.json",
    )
    retrieve.add_argument("--catalog", type=Path, default=DEFAULT_OUTPUT)
    retrieve.add_argument("--input-dir", type=Path, default=DEFAULT_QUERY_INPUT)
    retrieve.add_argument(
        "--output-dir", type=Path, default=OUTPUT_DIR / "retrieval"
    )
    retrieve.add_argument("--top-k", type=int, default=20)
    retrieve.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    retrieve.add_argument("--keyword-workers", type=int, default=8)
    retrieve.add_argument(
        "--semantic-weight", type=float, default=DEFAULT_SEMANTIC_WEIGHT
    )
    retrieve.add_argument(
        "--keyword-weight", type=float, default=DEFAULT_KEYWORD_WEIGHT
    )
    return parser


def command_inventory(args):
    files = discover_files(args.input_dir)
    counts = Counter(path.suffix.lower() for path in files)
    metadata = CollectorMetadata.load(args.collector_json)
    print(f"input_dir={args.input_dir.resolve()}")
    print(f"files={len(files)}")
    print(f"extensions={json.dumps(dict(sorted(counts.items())), ensure_ascii=False)}")
    print(f"collector_records={len(metadata.records)}")


def command_inspect(args):
    print(json.dumps(inspect_file(args.file, args.max_chars), ensure_ascii=False, indent=2))


def command_check_api(args):
    settings = Settings.from_env()
    client = InfereraClient(settings)
    context = {
        "document_id": "doc_api_check",
        "source_filename": "api_check.pdf",
        "extension": ".pdf",
        "crawler": {
            "title": "甲公司 2024 年年度报告",
            "query": "甲公司 年度报告 filetype:pdf",
        },
        "extraction": {"method": "synthetic", "characters": 76},
    }
    content = (
        "甲公司2024年年度报告。报告期为2024年1月1日至2024年12月31日，"
        "主要介绍融资租赁业务、经营情况和年度财务信息。发布日期为2025年4月。"
    )
    profile = client.analyze(context, content)
    print(
        f"api_ok=true model={settings.model} summary_chars={len(profile.summary)} "
        f"document_type={profile.document_type}"
    )
    if args.show_result:
        print(profile.model_dump_json(indent=2, exclude_none=True))


def command_schema(args):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(DocumentRecord.model_json_schema(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"schema={args.output.resolve()}")


def command_run(args):
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    settings = Settings.from_env()
    files = discover_files(args.input_dir)
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be at least 1")
        files = files[: args.limit]
    metadata = CollectorMetadata.load(args.collector_json)
    processor = DocumentProcessor(settings, InfereraClient(settings), metadata)
    run_batch(
        processor,
        files,
        args.checkpoint,
        args.output,
        workers=args.workers,
        retry_failed=args.retry_failed,
    )


def command_query_schema(args):
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            TypeAdapter(list[QueryDraft]).json_schema(),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"schema={args.output.resolve()}")


def command_generate_queries(args):
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    catalog = load_catalog(args.catalog)
    files = discover_files(args.input_dir)
    if args.source_file:
        requested = set(args.source_file)
        available = {path.name for path in files}
        missing = sorted(requested - available)
        if missing:
            raise SystemExit(f"source files not found: {', '.join(missing)}")
        files = [path for path in files if path.name in requested]
    files = [path for path in files if path.name in catalog]
    if args.limit is not None:
        files = files[: args.limit]
    if not files:
        raise SystemExit("no cataloged input files selected")
    settings = Settings.from_env()
    client = GDPvalQueryClient(settings)
    processor = QueryProcessor(settings, client, catalog)
    run_query_batch(
        processor,
        files,
        args.checkpoint,
        args.output,
        workers=args.workers,
        retry_failed=args.retry_failed,
    )


def command_retrieve_attachments(args):
    queries = load_queries(args.queries)
    settings = Settings.from_env()
    keyword_client = QueryKeywordClient(settings)
    keyword_cache = Path(args.output_dir).resolve() / "query_keywords.json"
    query_keywords = load_or_extract_query_keywords(
        queries,
        keyword_client,
        keyword_cache,
        workers=args.keyword_workers,
    )
    manifest = retrieve_attachments(
        queries_path=args.queries,
        query_keywords=query_keywords,
        catalog_path=args.catalog,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        top_k=args.top_k,
        model_name=args.model,
        semantic_weight=args.semantic_weight,
        keyword_weight=args.keyword_weight,
        keyword_metadata={
            "model": keyword_client.settings.model,
            "prompt_version": keyword_client.prompt_version,
            "prompt_sha256": keyword_client.prompt_sha256,
            "cache_file": str(keyword_cache),
        },
    )
    for item in manifest["queries"]:
        print(
            f"[retrieve] query={item['query_index']} "
            f"results={len(item['results'])} directory={item['directory']}"
        )
    print(
        f"[retrieve] done queries={len(manifest['queries'])} "
        f"top_k={manifest['top_k']} output={Path(args.output_dir).resolve()}"
    )


def main():
    args = build_parser().parse_args()
    commands = {
        "inventory": command_inventory,
        "inspect": command_inspect,
        "check-api": command_check_api,
        "schema": command_schema,
        "run": command_run,
        "query-schema": command_query_schema,
        "generate-queries": command_generate_queries,
        "retrieve-attachments": command_retrieve_attachments,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
