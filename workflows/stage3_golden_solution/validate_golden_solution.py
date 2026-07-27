#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path
import zipfile

import fitz
import openpyxl
from docx import Document


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DELIVERABLE_PATTERN = re.compile(
    r"(?m)^\s*\d+[.、]\s+`([^`\n]+\.(?:docx|xlsx|pptx|pdf|csv|md|txt))`"
)
PLACEHOLDER_PATTERN = re.compile(
    r"\bTODO\b|待补充|待填写|示例数据|placeholder",
    re.IGNORECASE,
)
NESTED_FORMULA_EQUALS_PATTERN = re.compile(r"=[A-Z][A-Z0-9_.]*\(")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def expected_deliverables(query):
    section = query.split("## 交付要求", 1)
    if len(section) != 2:
        raise ValueError("query does not contain a 交付要求 section")
    filenames = DELIVERABLE_PATTERN.findall(section[1])
    if not 1 <= len(filenames) <= 5:
        raise ValueError(
            f"expected 1-5 named deliverables in query, found {len(filenames)}"
        )
    if len(filenames) != len(set(filenames)):
        raise ValueError("query contains duplicate deliverable filenames")
    return filenames


def inspect_docx(path):
    document = Document(path)
    paragraph_text = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]
    table_text = [
        cell.text.strip()
        for table in document.tables
        for row in table.rows
        for cell in row.cells
        if cell.text.strip()
    ]
    text = "\n".join(paragraph_text + table_text)
    if len(text) < 1000:
        raise ValueError(f"{path.name}: Word content is too short")
    if PLACEHOLDER_PATTERN.search(text):
        raise ValueError(f"{path.name}: contains placeholder content")
    return {
        "paragraphs": len(paragraph_text),
        "tables": len(document.tables),
        "text_chars": len(text),
    }


def inspect_xlsx(path):
    workbook = openpyxl.load_workbook(path, data_only=False, read_only=False)
    nonempty_cells = 0
    formulas = 0
    invalid_formulas = []
    text_parts = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                nonempty_cells += 1
                text_parts.append(str(cell.value))
                if cell.data_type == "f":
                    formulas += 1
                    formula_body = str(cell.value)[1:]
                    if (
                        NESTED_FORMULA_EQUALS_PATTERN.search(formula_body)
                        or any(
                            operator in formula_body
                            for operator in ("+=", "-=", "*=", "/=")
                        )
                    ):
                        invalid_formulas.append(
                            f"{worksheet.title}!{cell.coordinate}"
                        )
    sheet_names = workbook.sheetnames
    workbook.close()
    if nonempty_cells < 50:
        raise ValueError(f"{path.name}: Excel content is too sparse")
    if formulas < 10:
        raise ValueError(f"{path.name}: expected at least 10 formulas")
    if invalid_formulas:
        locations = ", ".join(invalid_formulas[:10])
        raise ValueError(
            f"{path.name}: contains syntactically suspicious formulas at {locations}"
        )
    if PLACEHOLDER_PATTERN.search("\n".join(text_parts)):
        raise ValueError(f"{path.name}: contains placeholder content")
    return {
        "worksheets": sheet_names,
        "nonempty_cells": nonempty_cells,
        "formulas": formulas,
        "suspicious_formulas": 0,
    }


def inspect_file(path):
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return inspect_docx(path)
    if suffix == ".xlsx":
        return inspect_xlsx(path)
    if suffix == ".pdf":
        with fitz.open(path) as document:
            if document.page_count < 1:
                raise ValueError(f"{path.name}: PDF has no pages")
            return {"pages": document.page_count}
    if suffix == ".pptx":
        with zipfile.ZipFile(path) as archive:
            slides = [
                name
                for name in archive.namelist()
                if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
            ]
        if not slides:
            raise ValueError(f"{path.name}: PowerPoint has no slides")
        return {"slides": len(slides)}
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        raise ValueError(f"{path.name}: text deliverable is too short")
    if PLACEHOLDER_PATTERN.search(text):
        raise ValueError(f"{path.name}: contains placeholder content")
    return {"text_chars": len(text)}


def validate(task_dir):
    final_dir = task_dir / "final"
    golden_dir = task_dir / "golden solution"
    query = (final_dir / "query.md").read_text(encoding="utf-8")
    filenames = expected_deliverables(query)

    if not golden_dir.is_dir():
        raise FileNotFoundError(golden_dir)
    actual_files = sorted(
        path.name for path in golden_dir.iterdir() if path.is_file()
    )
    if sorted(filenames) != actual_files:
        raise ValueError(
            "golden solution files do not match query deliverables: "
            f"expected={sorted(filenames)} actual={actual_files}"
        )

    inspections = {}
    for filename in filenames:
        path = golden_dir / filename
        inspections[filename] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            **inspect_file(path),
        }

    internal_dir = golden_dir / "internal"
    for filename in (
        "source_traceability.md",
        "validation_report.json",
        "solution_manifest.json",
    ):
        path = internal_dir / filename
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(path)

    manifest = json.loads(
        (internal_dir / "solution_manifest.json").read_text(encoding="utf-8")
    )
    records = manifest.get("deliverables", [])
    if {record.get("filename") for record in records} != set(filenames):
        raise ValueError("solution manifest deliverables do not match query")
    by_name = {record["filename"]: record for record in records}
    for filename, inspection in inspections.items():
        record = by_name[filename]
        if record.get("sha256") != inspection["sha256"]:
            raise ValueError(f"{filename}: solution manifest SHA-256 mismatch")
        if record.get("bytes") != inspection["bytes"]:
            raise ValueError(f"{filename}: solution manifest byte size mismatch")

    return {
        "task": task_dir.name,
        "deliverables": len(filenames),
        "files": inspections,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate generated Golden Solution files."
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

    result = validate(args.workspace / f"task_{args.task}")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
