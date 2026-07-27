#!/usr/bin/env python3
"""Stage 2: prepare isolated workspaces and let Claude Code build each task."""

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = (
    PROJECT_ROOT / "output" / "stage1_query_retrieval" / "retrieval" / "manifest.json"
)
DEFAULT_TASKS_DIR = PROJECT_ROOT / "output" / "tasks"


def command_text(command):
    return shlex.join(str(item) for item in command)


def run_command(command, check=True):
    print(f"[stage2] run: {command_text(command)}", flush=True)
    return subprocess.run(
        [str(item) for item in command],
        cwd=PROJECT_ROOT,
        check=check,
    )


def command_succeeds(command):
    return (
        subprocess.run(
            [str(item) for item in command],
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def available_indexes(manifest_path):
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    queries = payload.get("queries", [])
    if not queries:
        raise ValueError("retrieval manifest does not contain query candidate sets")
    indexes = []
    for query in queries:
        index = int(query["query_index"])
        if len(query.get("results", [])) != 20:
            raise ValueError(f"query {index:03d} must contain exactly 20 candidates")
        indexes.append(index)
    return indexes


def select_indexes(available, requested):
    if not requested:
        return available
    selected = sorted(set(requested))
    missing = sorted(set(selected) - set(available))
    if missing:
        raise ValueError(f"query indexes not found in manifest: {missing}")
    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Prepare Top 20 workspaces and run Claude Code task construction."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument(
        "--task-index",
        type=int,
        action="append",
        help="One-based query index; may be repeated.",
    )
    parser.add_argument(
        "--stop-after",
        choices=("prepare", "task"),
        default="task",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.resume and args.force:
        raise SystemExit("--resume and --force cannot be used together")
    manifest_path = args.manifest.resolve()
    tasks_dir = args.tasks_dir.resolve()
    indexes = select_indexes(
        available_indexes(manifest_path),
        args.task_index,
    )

    for index in indexes:
        task_id = f"{index:03d}"
        task_dir = tasks_dir / f"task_{task_id}"
        candidate_manifest = task_dir / "candidate_manifest.json"
        prepare_command = [
            Path(sys.executable),
            WORKFLOW_DIR / "prepare_workspace.py",
            "--manifest",
            manifest_path,
            "--tasks-dir",
            tasks_dir,
            "--task",
            task_id,
        ]
        if args.force:
            prepare_command.append("--force")
        validator = [
            Path(sys.executable),
            WORKFLOW_DIR / "validate_task_output.py",
            "--workspace",
            tasks_dir,
            "--task",
            task_id,
        ]
        claude_command = [
            "bash",
            WORKFLOW_DIR / "run_claude_task.sh",
            task_id,
            tasks_dir,
        ]

        if args.dry_run:
            print(command_text(prepare_command))
            if args.stop_after == "task":
                print(command_text(claude_command))
                print(command_text(validator))
            continue

        prepared = False
        if args.resume and candidate_manifest.is_file():
            payload = json.loads(candidate_manifest.read_text(encoding="utf-8"))
            prepared = payload.get("candidate_count") == 20
        if prepared:
            print(f"[stage2] skip prepare task={task_id}")
        else:
            if args.resume and task_dir.exists() and "--force" not in prepare_command:
                prepare_command.append("--force")
            run_command(prepare_command)

        if args.stop_after == "prepare":
            continue
        if args.resume and command_succeeds(validator):
            print(f"[stage2] skip Claude task={task_id}: validation passed")
            continue

        claude_result = run_command(claude_command, check=False)
        if claude_result.returncode:
            print(
                f"[stage2] warning: Claude exited with {claude_result.returncode}; "
                "checking actual files",
                flush=True,
            )
        run_command(validator)

    print(
        f"[stage2] complete tasks={','.join(f'{index:03d}' for index in indexes)} "
        f"output={tasks_dir}"
    )


if __name__ == "__main__":
    main()
