import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_end_to_end.py"
)
SPEC = importlib.util.spec_from_file_location("end_to_end", SCRIPT_PATH)
PIPELINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PIPELINE)


def test_load_query_items_normalizes_strings_and_objects(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps([" 第一题 ", {"query": "第二题"}], ensure_ascii=False),
        encoding="utf-8",
    )

    assert PIPELINE.load_query_items(path) == [
        {"query": "第一题"},
        {"query": "第二题"},
    ]


def test_load_query_items_accepts_queries_wrapper(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps({"queries": [{"query": "测试任务"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    assert PIPELINE.load_query_items(path) == [{"query": "测试任务"}]


def test_load_query_items_rejects_non_string_items(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text("[42]", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid"):
        PIPELINE.load_query_items(path)


@pytest.mark.parametrize("value", ["../bad", "包含中文", "", "bad/name"])
def test_validate_run_id_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        PIPELINE.validate_run_id(value)


def test_select_task_indexes_checks_query_range():
    assert PIPELINE.select_task_indexes(3, [3, 1, 3]) == [1, 3]

    with pytest.raises(ValueError, match="outside"):
        PIPELINE.select_task_indexes(2, [3])
