from types import SimpleNamespace

from finance_forensics.config import PROMPT_DIR
from finance_forensics.keyword_llm import (
    QueryKeywordClient,
    load_or_extract_query_keywords,
    normalize_keyword_payload,
)
from finance_forensics.models import QueryKeywordsDraft


def test_normalize_keyword_payload_deduplicates_and_limits():
    payload = {
        "keywords": [
            "募集资金",
            " 约定用途 ",
            "募集资金",
            "投资者保护",
            "偿债保障",
            "使用合规性",
            "风险触发",
            "资金流向",
            "债券条款",
            "信息披露",
            "救济措施",
            "资金闲置",
            "项目进展",
            "额外关键词",
        ]
    }
    normalized = normalize_keyword_payload(payload)
    assert len(normalized["keywords"]) == 8
    assert normalized["keywords"][:2] == ["募集资金", "约定用途"]


def test_keyword_prompt_contains_query_and_schema():
    client = QueryKeywordClient.__new__(QueryKeywordClient)
    client.user_prompt_template = (
        PROMPT_DIR / "检索关键词输入模板.md"
    ).read_text(encoding="utf-8")
    result = client.build_user_prompt("核验募集资金实际用途与约定是否一致。")
    assert '"keywords"' in result
    assert "募集资金实际用途" in result


def test_keyword_cache_skips_completed_queries(tmp_path):
    class FakeClient:
        prompt_version = "test_v1"
        settings = SimpleNamespace(model="test-model")

        def __init__(self):
            self.calls = []

        def extract(self, query):
            self.calls.append(query)
            return QueryKeywordsDraft(
                keywords=["关键词一", "关键词二", "关键词三", "关键词四", "关键词五"]
            )

    queries = ["第一条检索任务", "第二条检索任务"]
    client = FakeClient()
    cache_path = tmp_path / "query_keywords.json"

    first = load_or_extract_query_keywords(
        queries, client, cache_path, workers=2
    )
    second = load_or_extract_query_keywords(
        queries, client, cache_path, workers=2
    )

    assert len(first) == 2
    assert first == second
    assert sorted(client.calls) == sorted(queries)
