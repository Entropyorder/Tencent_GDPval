#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def export_query_markdown(task_dir):
    query_path = task_dir / "final" / "query.json"
    payload = json.loads(query_path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, list)
        or len(payload) != 1
        or set(payload[0]) != {"query"}
        or not isinstance(payload[0]["query"], str)
        or not payload[0]["query"].strip()
    ):
        raise ValueError(f"{query_path}: expected one object with a query string")

    output_path = task_dir / "final" / "query.md"
    output_path.write_text(payload[0]["query"].strip() + "\n", encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Export a readable Markdown copy of a task query."
    )
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=PROJECT_ROOT / "output" / "tasks",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"\d{3}", args.task):
        raise SystemExit("--task must be a three-digit ID")

    output_path = export_query_markdown(
        args.workspace / f"task_{args.task}"
    )
    print(output_path)


if __name__ == "__main__":
    main()
