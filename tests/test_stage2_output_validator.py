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
    deliverables = "\n".join(
        f"{index}. `交付文件{index}.xlsx`：包含对应分析。"
        for index in range(1, deliverable_count + 1)
    )
    return (
        "## 任务背景\n"
        "你是一名信用分析师，需要为投资委员会准备决策材料。\n\n"
        "## 具体任务\n"
        "请综合所提供材料，对相关主体的经营质量、财务韧性与风险暴露进行"
        "系统评估，在处理报告期、口径和信息完整度差异的基础上形成可复核的"
        "专业判断，并构建能够支持投资委员会比较、压力评估和资源配置决策的"
        "一致分析框架。成果应体现跨材料验证、定量分析和行业洞察，同时明确"
        "重要不确定性与结论边界，为后续投资筛选和风险管理提供依据。\n\n"
        "## 交付要求\n"
        f"请提交以下 {deliverable_count} 个文件：\n"
        f"{deliverables}"
    )


def make_workflow(step_count=12):
    return "# 工作流程\n\n" + "\n".join(
        f"{index}. 完成第{index}项具有前后依赖关系的专业分析工作，并记录来源、"
        "计算过程、判断依据和质量检查结果。"
        for index in range(1, step_count + 1)
    )


def test_validate_query_design_accepts_narrative_task_and_separate_workflow():
    result = VALIDATOR.validate_query_design(make_query(5), make_workflow())

    assert result == {"workflow_steps": 12, "deliverable_files": 5}


def test_validate_query_design_rejects_more_than_five_files():
    with pytest.raises(ValueError, match="where N is 1-5"):
        VALIDATOR.validate_query_design(make_query(6), make_workflow())


def test_validate_query_design_rejects_missing_concrete_filename():
    query = make_query(2).replace(
        "`交付文件2.xlsx`：包含对应分析。",
        "提交第二项分析结果。",
    )

    with pytest.raises(ValueError, match="concrete filename"):
        VALIDATOR.validate_query_design(query, make_workflow())


def test_validate_query_design_rejects_fewer_than_twelve_workflow_steps():
    with pytest.raises(ValueError, match="at least 12 numbered steps"):
        VALIDATOR.validate_query_design(make_query(), make_workflow(11))


def test_validate_query_design_rejects_numbered_specific_tasks():
    query = make_query().replace(
        "请综合所提供材料",
        "1. 请综合所提供材料",
    )

    with pytest.raises(ValueError, match="must not contain lists or steps"):
        VALIDATOR.validate_query_design(query, make_workflow())


def test_validate_query_design_rejects_multiple_specific_task_paragraphs():
    query = make_query().replace(
        "成果应体现",
        "\n\n成果应体现",
    )

    with pytest.raises(ValueError, match="exactly one paragraph"):
        VALIDATOR.validate_query_design(query, make_workflow())


def test_validate_query_design_rejects_workflow_methods_in_specific_task():
    query = make_query().replace(
        "综合所提供材料",
        "逐份提取并计算所提供材料",
    )

    with pytest.raises(ValueError, match="workflow-level method guidance"):
        VALIDATOR.validate_query_design(query, make_workflow())


def test_validate_query_design_keeps_legacy_tasks_compatible():
    tasks = "\n".join(
        f"{index}. 完成第 {index} 项分析。" for index in range(1, 11)
    )
    legacy_query = make_query().replace(
        "请综合所提供材料，对相关主体的经营质量、财务韧性与风险暴露进行"
        "系统评估，在处理报告期、口径和信息完整度差异的基础上形成可复核的"
        "专业判断，并构建能够支持投资委员会比较、压力评估和资源配置决策的"
        "一致分析框架。成果应体现跨材料验证、定量分析和行业洞察，同时明确"
        "重要不确定性与结论边界，为后续投资筛选和风险管理提供依据。",
        tasks,
    )

    result = VALIDATOR.validate_query_design(legacy_query)

    assert result["workflow_steps"] == 10


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
