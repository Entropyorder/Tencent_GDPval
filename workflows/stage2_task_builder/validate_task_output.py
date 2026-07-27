#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERY_SECTION_TITLES = ("任务背景", "具体任务", "交付要求")
DELIVERABLE_FILE_PATTERN = re.compile(
    r"`[^`\n]+\.(?:docx|xlsx|pptx|pdf|csv|md|txt)`",
    re.IGNORECASE,
)
TASK_METHOD_PATTERN = re.compile(
    r"步骤|逐份|逐项|手工|提取|计算|页码|工作表|公式|权重|阈值|评分模型"
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def validate_workflow_design(workflow):
    if not workflow.strip():
        raise ValueError("workflow.md must not be empty")
    workflow_numbers = re.findall(r"(?m)^\s*(\d+)[.、]\s+", workflow)
    if len(workflow_numbers) < 12:
        raise ValueError(
            "workflow.md must contain at least 12 numbered steps, "
            f"found {len(workflow_numbers)}"
        )
    expected_numbers = [
        str(index) for index in range(1, len(workflow_numbers) + 1)
    ]
    if workflow_numbers != expected_numbers:
        raise ValueError("workflow numbering must be continuous from 1")
    return len(workflow_numbers)


def validate_query_design(query, workflow=None):
    headings = re.findall(r"(?m)^##\s+(.+?)\s*$", query)
    if tuple(headings) != QUERY_SECTION_TITLES:
        raise ValueError(
            "query must contain exactly these sections in order: "
            "任务背景, 具体任务, 交付要求"
        )

    sections = re.split(r"(?m)^##\s+.+?\s*$", query)
    if len(sections) != 4 or any(not section.strip() for section in sections[1:]):
        raise ValueError("query sections must all contain content")

    task_section = sections[2].strip()
    if workflow is None:
        task_numbers = re.findall(r"(?m)^\s*(\d+)[.、]\s+", task_section)
        if len(task_numbers) < 10:
            raise ValueError(
                "legacy query must contain at least 10 numbered tasks, "
                f"found {len(task_numbers)}"
            )
        expected_task_numbers = [
            str(index) for index in range(1, len(task_numbers) + 1)
        ]
        if task_numbers != expected_task_numbers:
            raise ValueError("query task numbering must be continuous from 1")
        workflow_steps = len(task_numbers)
    else:
        paragraphs = [
            item.strip()
            for item in re.split(r"\n\s*\n", task_section)
            if item.strip()
        ]
        if len(paragraphs) != 1:
            raise ValueError(
                "query specific-task section must be exactly one paragraph"
            )
        if re.search(r"(?m)^\s*(?:\d+[.、]|[-*+])\s+", task_section):
            raise ValueError(
                "query specific-task section must not contain lists or steps"
            )
        if not 120 <= len(task_section) <= 320:
            raise ValueError(
                "query specific-task paragraph must contain 120-320 characters"
            )
        method_match = TASK_METHOD_PATTERN.search(task_section)
        if method_match:
            raise ValueError(
                "query specific-task paragraph contains workflow-level method "
                f"guidance: {method_match.group(0)}"
            )
        workflow_steps = validate_workflow_design(workflow)

    deliverable_section = sections[3]
    match = re.search(r"请提交以下\s*([1-5])\s*个文件[：:]", deliverable_section)
    if not match:
        raise ValueError(
            "deliverable section must state: 请提交以下 N 个文件：, where N is 1-5"
        )
    declared_count = int(match.group(1))
    deliverable_lines = re.findall(
        r"(?m)^\s*(\d+)[.、]\s+(.+)$", deliverable_section
    )
    if len(deliverable_lines) != declared_count:
        raise ValueError(
            "declared deliverable count does not match the numbered file list"
        )
    expected_deliverable_numbers = [
        str(index) for index in range(1, declared_count + 1)
    ]
    if [number for number, _ in deliverable_lines] != expected_deliverable_numbers:
        raise ValueError("deliverable numbering must be continuous from 1")
    for _, line in deliverable_lines:
        if not DELIVERABLE_FILE_PATTERN.search(line):
            raise ValueError(
                "every deliverable must include a concrete filename with an extension"
            )

    return {
        "workflow_steps": workflow_steps,
        "deliverable_files": declared_count,
    }


def validate_query_markdown(query, markdown_path):
    if not markdown_path.is_file():
        raise FileNotFoundError(f"missing readable query copy: {markdown_path}")
    markdown = markdown_path.read_text(encoding="utf-8")
    if markdown.strip() != query.strip():
        raise ValueError("query.md must exactly match the query field in query.json")


def validate_task(task_dir):
    manifest = json.loads(
        (task_dir / "candidate_manifest.json").read_text(encoding="utf-8")
    )
    query_payload = json.loads(
        (task_dir / "final" / "query.json").read_text(encoding="utf-8")
    )
    if (
        not isinstance(query_payload, list)
        or len(query_payload) != 1
        or set(query_payload[0]) != {"query"}
        or not isinstance(query_payload[0]["query"], str)
        or not query_payload[0]["query"].strip()
    ):
        raise ValueError(f"{task_dir.name}: query.json must contain only one query")
    query_design = None
    query_markdown_path = task_dir / "final" / "query.md"
    workflow_path = task_dir / "final" / "workflow.md"
    if query_markdown_path.is_file():
        workflow = (
            workflow_path.read_text(encoding="utf-8")
            if workflow_path.is_file()
            else None
        )
        query_design = validate_query_design(query_payload[0]["query"], workflow)
        validate_query_markdown(
            query_payload[0]["query"],
            query_markdown_path,
        )
    elif task_dir.name != "task_001":
        raise FileNotFoundError(
            f"{task_dir.name}: missing readable query copy: {query_markdown_path}"
        )

    selection = json.loads(
        (task_dir / "final" / "internal" / "selection_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    attachments_dir = task_dir / "final" / "attachments"
    attachments = sorted(path for path in attachments_dir.iterdir() if path.is_file())
    if not 10 <= len(attachments) <= 17:
        raise ValueError(
            f"{task_dir.name}: expected 10-17 attachments, found {len(attachments)}"
        )

    selected_records = selection.get("attachments", [])
    if len(selected_records) != len(attachments):
        raise ValueError(f"{task_dir.name}: selection manifest count mismatch")
    if {item["filename"] for item in selected_records} != {
        path.name for path in attachments
    }:
        raise ValueError(f"{task_dir.name}: attachment filename mismatch")
    if workflow_path.is_file():
        expected_prefixes = [
            f"{position:02d}__"
            for position in range(1, len(selected_records) + 1)
        ]
        actual_prefixes = [
            item["filename"][:4] for item in selected_records
        ]
        if actual_prefixes != expected_prefixes:
            raise ValueError(
                f"{task_dir.name}: final attachment numbering must be "
                "continuous from 01"
            )

    candidates_by_id = {
        item["document_id"]: item for item in manifest["candidates"]
    }
    generated_count = 0
    for item in selected_records:
        path = attachments_dir / item["filename"]
        if item.get("sha256") != sha256(path):
            raise ValueError(f"{task_dir.name}: SHA-256 mismatch for {path.name}")
        if item.get("origin") == "generated":
            generated_count += 1
            continue
        if item.get("origin") != "candidate":
            raise ValueError(f"{task_dir.name}: invalid origin for {path.name}")
        document_id = item.get("document_id")
        if document_id not in candidates_by_id:
            raise ValueError(
                f"{task_dir.name}: attachment is outside its candidate set: {path.name}"
            )
        source = task_dir / candidates_by_id[document_id]["candidate_path"]
        if sha256(source) != sha256(path):
            raise ValueError(
                f"{task_dir.name}: candidate content mismatch for {path.name}"
            )

    if generated_count > 3:
        raise ValueError(
            f"{task_dir.name}: expected at most 3 generated files, "
            f"found {generated_count}"
        )
    if workflow_path.is_file() and generated_count < 1:
        raise ValueError(
            f"{task_dir.name}: expected at least 1 generated file in the "
            "final attachment set"
        )
    if not (task_dir / "final" / "internal" / "evidence_matrix.md").is_file():
        raise FileNotFoundError(f"{task_dir.name}: missing evidence_matrix.md")
    if not (task_dir / "final" / "internal" / "quality_review.md").is_file():
        raise FileNotFoundError(f"{task_dir.name}: missing quality_review.md")

    result = {
        "task": task_dir.name,
        "attachments": len(attachments),
        "candidate_attachments": len(attachments) - generated_count,
        "generated_attachments": generated_count,
        "query_chars": len(query_payload[0]["query"]),
    }
    if query_design:
        result.update(query_design)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Validate Stage 2 finance task deliverables."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=PROJECT_ROOT / "output" / "tasks",
    )
    parser.add_argument(
        "--task",
        action="append",
        help="Validate only this task ID; may be repeated. Defaults to both tasks.",
    )
    args = parser.parse_args()
    if args.task and any(not re.fullmatch(r"\d{3}", item) for item in args.task):
        raise SystemExit("--task values must be three-digit IDs")

    for task_id in args.task or ("001", "002"):
        result = validate_task(args.workspace / f"task_{task_id}")
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
