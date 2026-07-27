#!/usr/bin/env python3
"""Thin orchestrator for the three independently owned workflow stages."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "pipeline_runs"
DEFAULT_CATALOG = PROJECT_ROOT / "output" / "catalog" / "document_catalog.json"
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "source_documents"
STAGES = ("stage1", "stage2", "stage3")


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


def validate_run_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise ValueError(
            "run ID must be 1-64 ASCII letters, numbers, dots, underscores or hyphens"
        )
    return value


def select_task_indexes(total, requested):
    if not requested:
        return list(range(1, total + 1))
    selected = sorted(set(requested))
    invalid = [index for index in selected if not 1 <= index <= total]
    if invalid:
        raise ValueError(
            f"task indexes outside query input range 1-{total}: {invalid}"
        )
    return selected


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
    print(f"[pipeline] run: {command_text(command)}", flush=True)
    subprocess.run(
        [str(item) for item in command],
        cwd=PROJECT_ROOT,
        check=True,
    )


def reached(stage, stop_after):
    return STAGES.index(stage) <= STAGES.index(stop_after)


def main():
    parser = argparse.ArgumentParser(
        description="Run Stage 1, Stage 2 and Stage 3 through their public entrypoints."
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
    parser.add_argument(
        "--run-id",
        default=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--candidate-k", type=int, default=80)
    parser.add_argument(
        "--task-index",
        type=int,
        action="append",
        help="Run only this one-based query index; may be repeated.",
    )
    parser.add_argument("--stop-after", choices=STAGES, default="stage3")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run_id = validate_run_id(args.run_id)
    if args.resume and args.force:
        raise SystemExit("--resume and --force cannot be used together")
    if args.candidate_k < 20:
        raise SystemExit("--candidate-k must be at least 20")

    if args.queries:
        query_count = len(load_query_items(args.queries))
    elif args.query:
        query_count = len([item for item in args.query if item.strip()])
    else:
        query_count = len(args.source_file)
    if query_count < 1:
        raise SystemExit("at least one query or source file is required")
    selected_indexes = select_task_indexes(query_count, args.task_index)

    run_dir = args.output_root.resolve() / run_id
    stage1_dir = run_dir / "stage1"
    tasks_dir = run_dir / "stage2" / "tasks"
    manifest_path = run_dir / "pipeline_manifest.json"

    stage1_command = [
        Path(sys.executable),
        WORKFLOWS_DIR / "stage1_query_retrieval" / "run.py",
        "--output-dir",
        stage1_dir,
        "--catalog",
        args.catalog.resolve(),
        "--input-dir",
        args.input_dir.resolve(),
        "--workers",
        str(args.workers),
        "--candidate-k",
        str(args.candidate_k),
    ]
    if args.queries:
        stage1_command.extend(["--queries", args.queries.resolve()])
    elif args.query:
        for query in args.query:
            stage1_command.extend(["--query", query])
    else:
        for source_file in args.source_file:
            stage1_command.extend(["--source-file", source_file])

    stage2_command = [
        Path(sys.executable),
        WORKFLOWS_DIR / "stage2_task_builder" / "run.py",
        "--manifest",
        stage1_dir / "retrieval" / "manifest.json",
        "--tasks-dir",
        tasks_dir,
    ]
    stage3_command = [
        Path(sys.executable),
        WORKFLOWS_DIR / "stage3_golden_solution" / "run.py",
        "--tasks-dir",
        tasks_dir,
    ]
    for index in selected_indexes:
        stage2_command.extend(["--task-index", str(index)])
        stage3_command.extend(["--task-index", str(index)])
    if args.resume:
        stage1_command.append("--resume")
        stage2_command.append("--resume")
        stage3_command.append("--resume")

    if args.dry_run:
        print(f"run_dir={run_dir}")
        print(f"selected_tasks={[f'{index:03d}' for index in selected_indexes]}")
        for stage, command in zip(
            STAGES,
            (stage1_command, stage2_command, stage3_command),
        ):
            if reached(stage, args.stop_after):
                print(command_text(command))
        return

    if args.force and run_dir.exists():
        shutil.rmtree(run_dir)
    elif run_dir.exists() and not args.resume:
        raise SystemExit(
            f"run directory already exists: {run_dir}; use --resume or --force"
        )
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": "2.0",
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "query_count": query_count,
        "selected_tasks": [f"{index:03d}" for index in selected_indexes],
        "paths": {
            "run": str(run_dir),
            "stage1_queries": str(stage1_dir / "queries.json"),
            "stage1_retrieval_manifest": str(
                stage1_dir / "retrieval" / "manifest.json"
            ),
            "stage2_tasks": str(tasks_dir),
        },
        "stages": {},
    }
    if args.resume and manifest_path.is_file():
        previous = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["created_at"] = previous.get("created_at", manifest["created_at"])
        manifest["stages"] = previous.get("stages", {})
    write_json(manifest_path, manifest)

    for stage, command in zip(
        STAGES,
        (stage1_command, stage2_command, stage3_command),
    ):
        if not reached(stage, args.stop_after):
            continue
        run_command(command)
        manifest["stages"][stage] = "completed"
        write_json(manifest_path, manifest)

    manifest["finished_at"] = datetime.now().astimezone().isoformat(
        timespec="seconds"
    )
    write_json(manifest_path, manifest)
    print(f"[pipeline] complete through={args.stop_after} output={run_dir}")


if __name__ == "__main__":
    main()
