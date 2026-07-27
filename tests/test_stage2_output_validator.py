import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "stage2_task_builder"
    / "validate_task_output.py"
)
SPEC = importlib.util.spec_from_file_location("stage2_output_validator", SCRIPT_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def make_query(deliverable_count=2):
    tasks = "\n".join(f"{index}. 完成第 {index} 项分析。" for index in range(1, 11))
    deliverables = "\n".join(
        f"{index}. `交付文件{index}.xlsx`：包含对应分析。"
        for index in range(1, deliverable_count + 1)
    )
    return (
        "## 任务背景\n"
        "你是一名信用分析师，需要为投资委员会准备决策材料。\n\n"
        "## 具体任务\n"
        f"{tasks}\n\n"
        "## 交付要求\n"
        f"请提交以下 {deliverable_count} 个文件：\n"
        f"{deliverables}"
    )


def test_validate_query_design_accepts_three_sections_and_five_or_fewer_files():
    result = VALIDATOR.validate_query_design(make_query(5))

    assert result == {"workflow_steps": 10, "deliverable_files": 5}


def test_validate_query_design_rejects_more_than_five_files():
    with pytest.raises(ValueError, match="where N is 1-5"):
        VALIDATOR.validate_query_design(make_query(6))


def test_validate_query_design_rejects_missing_concrete_filename():
    query = make_query(2).replace(
        "`交付文件2.xlsx`：包含对应分析。",
        "提交第二项分析结果。",
    )

    with pytest.raises(ValueError, match="concrete filename"):
        VALIDATOR.validate_query_design(query)


def test_validate_query_design_rejects_fewer_than_ten_tasks():
    query = make_query(2).replace("10. 完成第 10 项分析。\n\n", "\n")

    with pytest.raises(ValueError, match="at least 10 numbered tasks"):
        VALIDATOR.validate_query_design(query)


def test_validate_query_markdown_accepts_exact_copy(tmp_path):
    query = make_query(2)
    markdown_path = tmp_path / "query.md"
    markdown_path.write_text(query + "\n", encoding="utf-8")

    VALIDATOR.validate_query_markdown(query, markdown_path)


def test_validate_query_markdown_rejects_different_copy(tmp_path):
    query = make_query(2)
    markdown_path = tmp_path / "query.md"
    markdown_path.write_text(query + "\n额外内容\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exactly match"):
        VALIDATOR.validate_query_markdown(query, markdown_path)
