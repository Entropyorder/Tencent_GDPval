import json
import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "workflows"
    / "stage3_golden_solution"
    / "validate_golden_solution.py"
)
SPEC = importlib.util.spec_from_file_location("golden_validator", SCRIPT_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def test_expected_deliverables_reads_named_files():
    query = (
        "## 任务背景\n背景\n\n"
        "## 具体任务\n1. 分析。\n\n"
        "## 交付要求\n请提交以下2个文件：\n"
        "1. `分析报告.docx`：报告。\n"
        "2. `计算模型.xlsx`：模型。\n"
    )

    assert VALIDATOR.expected_deliverables(query) == [
        "分析报告.docx",
        "计算模型.xlsx",
    ]


def test_expected_deliverables_rejects_duplicate_names():
    query = (
        "## 交付要求\n"
        "1. `分析报告.docx`：第一份。\n"
        "2. `分析报告.docx`：第二份。\n"
    )

    with pytest.raises(ValueError, match="duplicate"):
        VALIDATOR.expected_deliverables(query)


def test_nested_formula_equals_pattern_flags_concatenated_formula():
    invalid = '=IF(OR(=IFERROR(A1,0)="缺失"),0,1)'
    valid = '=IF(OR(IFERROR(A1,0)="缺失"),0,1)'

    assert VALIDATOR.NESTED_FORMULA_EQUALS_PATTERN.search(invalid[1:])
    assert not VALIDATOR.NESTED_FORMULA_EQUALS_PATTERN.search(valid[1:])


def test_financial_resource_usage_maps_skill_and_compatible_templates(tmp_path):
    task_dir = tmp_path / "task_999"
    final_internal = task_dir / "final" / "internal"
    golden_internal = task_dir / "golden solution" / "internal"
    final_internal.mkdir(parents=True)
    golden_internal.mkdir(parents=True)
    filenames = ["分析报告.docx", "测算模型.xlsx"]
    contract = {
        "skill": {"name": "generating-financial-analysis-reports"},
        "templates": [
            {
                "id": "financial-analysis-report-doc",
                "golden_formats": ["docx"],
            },
            {
                "id": "valuation-model-xlsx",
                "golden_formats": ["xlsx"],
            },
        ],
    }
    usage = {
        "skill": {
            "name": "generating-financial-analysis-reports",
            "applied_to": filenames,
            "principles": ["自然财务写作", "来源可追溯"],
        },
        "templates": [
            {
                "id": "financial-analysis-report-doc",
                "applied_to": ["分析报告.docx"],
                "adaptations": ["采用正式章节层级和三线表"],
                "copied_source_data": False,
            },
            {
                "id": "valuation-model-xlsx",
                "applied_to": ["测算模型.xlsx"],
                "adaptations": ["采用输入、计算、结果和检查分层"],
                "copied_source_data": False,
            },
        ],
    }
    (final_internal / "financial_resources.json").write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8"
    )
    usage_path = golden_internal / "resource_usage.json"
    usage_path.write_text(
        json.dumps(usage, ensure_ascii=False), encoding="utf-8"
    )

    result = VALIDATOR.validate_financial_resource_usage(
        task_dir, golden_internal, filenames
    )

    assert result["templates"] == 2
    assert result["covered_deliverables"] == 2

    usage["templates"][0]["copied_source_data"] = True
    usage_path.write_text(
        json.dumps(usage, ensure_ascii=False), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="copied_source_data=false"):
        VALIDATOR.validate_financial_resource_usage(
            task_dir, golden_internal, filenames
        )
