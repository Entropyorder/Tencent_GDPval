#!/usr/bin/env python3
"""Stage 1: create/normalize queries and retrieve exactly 20 candidates each."""

import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = PROJECT_ROOT / "output" / "catalog" / "document_catalog.json"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "source_documents"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "output" / "stage1_query_retrieval"


def load_query_items(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "queries" in payload:
        payload = payload["queries"]
    if not isinstance(payload, list):
        raise ValueError("query input must be a JSON array or an object with queries")

    queries = []
    for index, item in enumerate(payload, start=1):
        query = (
            item
            if isinstance(item, str)
            else item.get("query")
            if isinstance(item, dict)
            else None
        )
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"query item {index} is empty or invalid")
        queries.append({"query": query.strip()})
    if not queries:
        raise ValueError("query input is empty")
    return queries


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def command_text(command):
    return shlex.join(str(item) for item in command)


def run_command(command):
    print(f"[stage1] run: {command_text(command)}", flush=True)
    subprocess.run(
        [str(item) for item in command],
        cwd=PROJECT_ROOT,
        check=True,
    )


def retrieval_is_valid(path, expected_count):
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    queries = payload.get("queries", [])
    return (
        len(queries) == expected_count
        and all(len(query.get("results", [])) == 20 for query in queries)
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate or normalize queries, then retrieve Top 20 documents."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--queries", type=Path, help="Existing query JSON.")
    source.add_argument(
        "--query",
        action="append",
        help="Query text; may be repeated.",
    )
    source.add_argument(
        "--source-file",
        action="append",
        help="Cataloged source filename used to generate a query; may be repeated.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--candidate-k", type=int, default=80)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.resume and args.force:
        raise SystemExit("--resume and --force cannot be used together")
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1")
    if args.candidate_k < 20:
        raise SystemExit("--candidate-k must be at least 20")

    output_dir = args.output_dir.resolve()
    queries_path = output_dir / "queries.json"
    checkpoint_path = output_dir / "query_checkpoint.jsonl"
    retrieval_dir = output_dir / "retrieval"
    retrieval_manifest = retrieval_dir / "manifest.json"

    query_generation_command = None
    direct_queries = None
    if args.queries:
        direct_queries = load_query_items(args.queries)
    elif args.query:
        direct_queries = [
            {"query": query.strip()}
            for query in args.query
            if isinstance(query, str) and query.strip()
        ]
        if not direct_queries:
            raise SystemExit("at least one non-empty --query is required")
    else:
        query_generation_command = [
            Path(sys.executable),
            "-m",
            "finance_forensics.cli",
            "generate-queries",
            "--input-dir",
            args.input_dir.resolve(),
            "--catalog",
            args.catalog.resolve(),
            "--output",
            queries_path,
            "--checkpoint",
            checkpoint_path,
            "--workers",
            str(args.workers),
        ]
        for source_file in args.source_file:
            query_generation_command.extend(["--source-file", source_file])

    retrieval_command = [
        Path(sys.executable),
        "-m",
        "finance_forensics.cli",
        "retrieve-attachments",
        "--queries",
        queries_path,
        "--catalog",
        args.catalog.resolve(),
        "--input-dir",
        args.input_dir.resolve(),
        "--output-dir",
        retrieval_dir,
        "--top-k",
        "20",
        "--candidate-k",
        str(args.candidate_k),
    ]

    if args.dry_run:
        print(f"queries={queries_path}")
        print(f"retrieval_manifest={retrieval_manifest}")
        if query_generation_command:
            print(command_text(query_generation_command))
        else:
            print(f"[stage1] write {len(direct_queries)} normalized queries")
        print(command_text(retrieval_command))
        return

    if args.force and output_dir.exists():
        shutil.rmtree(output_dir)
    elif output_dir.exists() and not args.resume:
        raise SystemExit(
            f"output directory already exists: {output_dir}; use --resume or --force"
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    if direct_queries is not None:
        if queries_path.is_file():
            existing_queries = load_query_items(queries_path)
            if existing_queries != direct_queries:
                raise SystemExit("resume query input differs from existing queries.json")
        else:
            write_json(queries_path, direct_queries)
    elif not (args.resume and queries_path.is_file()):
        run_command(query_generation_command)

    normalized_queries = load_query_items(queries_path)
    if args.resume and retrieval_is_valid(
        retrieval_manifest, len(normalized_queries)
    ):
        print("[stage1] skip retrieval: existing Top 20 manifest is valid")
    else:
        run_command(retrieval_command)

    if not retrieval_is_valid(retrieval_manifest, len(normalized_queries)):
        raise SystemExit("retrieval output is invalid: every query must have Top 20")
    print(
        f"[stage1] complete queries={len(normalized_queries)} "
        f"manifest={retrieval_manifest}"
    )


if __name__ == "__main__":
    main()
