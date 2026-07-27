#!/usr/bin/env python3
"""Stage 3: create or repair and validate Golden Solutions."""

import argparse
from pathlib import Path
import re
import shlex
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = Path(__file__).resolve().parent
DEFAULT_TASKS_DIR = PROJECT_ROOT / "output" / "tasks"


def command_text(command):
    return shlex.join(str(item) for item in command)


def run_command(command, check=True):
    print(f"[stage3] run: {command_text(command)}", flush=True)
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


def discover_indexes(tasks_dir):
    indexes = []
    for path in sorted(tasks_dir.glob("task_???")):
        match = re.fullmatch(r"task_(\d{3})", path.name)
        if match and (path / "final" / "query.json").is_file():
            indexes.append(int(match.group(1)))
    return indexes


def select_indexes(tasks_dir, requested):
    available = discover_indexes(tasks_dir)
    if requested:
        selected = sorted(set(requested))
        missing = sorted(set(selected) - set(available))
        if missing:
            raise ValueError(f"completed Stage 2 tasks not found: {missing}")
        return selected
    if not available:
        raise ValueError(f"no completed Stage 2 tasks found in {tasks_dir}")
    return available


def main():
    parser = argparse.ArgumentParser(
        description="Generate and validate Golden Solutions for completed tasks."
    )
    parser.add_argument("--tasks-dir", type=Path, default=DEFAULT_TASKS_DIR)
    parser.add_argument(
        "--task-index",
        type=int,
        action="append",
        help="One-based task index; may be repeated.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Repair an existing invalid Golden Solution.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tasks_dir = args.tasks_dir.resolve()
    indexes = select_indexes(tasks_dir, args.task_index)
    for index in indexes:
        task_id = f"{index:03d}"
        golden_dir = tasks_dir / f"task_{task_id}" / "golden solution"
        validator = [
            Path(sys.executable),
            WORKFLOW_DIR / "validate_golden_solution.py",
            "--workspace",
            tasks_dir,
            "--task",
            task_id,
        ]
        command = [
            "bash",
            WORKFLOW_DIR / "run_claude_golden_solution.sh",
            task_id,
            tasks_dir,
        ]
        repair = args.repair or golden_dir.exists()
        if repair:
            command.append("--repair")

        if args.dry_run:
            print(command_text(command))
            print(command_text(validator))
            continue
        if args.resume and command_succeeds(validator):
            print(f"[stage3] skip task={task_id}: validation passed")
            continue

        result = run_command(command, check=False)
        if result.returncode:
            print(
                f"[stage3] warning: Claude exited with {result.returncode}; "
                "checking actual files",
                flush=True,
            )
        run_command(validator)

    print(
        f"[stage3] complete tasks={','.join(f'{index:03d}' for index in indexes)} "
        f"output={tasks_dir}"
    )


if __name__ == "__main__":
    main()
