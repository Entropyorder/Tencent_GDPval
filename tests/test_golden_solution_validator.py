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
