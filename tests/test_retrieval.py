import json

import numpy as np

from finance_forensics.retrieval import (
    build_document_text,
    build_keyword_document_text,
    catalog_attachment_filename,
    combine_retrieval_scores,
    load_queries,
    minmax,
)


def test_load_queries_accepts_query_only_records(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps([{"query": "信用风险分析"}, {"query": "经营表现分析"}]),
        encoding="utf-8",
    )
    assert load_queries(path) == ["信用风险分析", "经营表现分析"]


def test_build_document_text_uses_only_summary_for_semantic_matching():
    text = build_document_text(
        {
            "document_type": "rating_report",
            "business_topic": "信用风险",
            "industry": "金融",
            "keywords": ["评级", "偿债"],
            "summary": "某份评级资料的摘要。",
        }
    )
    assert text == "某份评级资料的摘要。"


def test_build_keyword_document_text_uses_catalog_profile():
    text = build_keyword_document_text(
        {
            "business_topic": "募集资金用途核查",
            "keywords": ["募集资金", "约定用途"],
            "summary": "核验实际资金使用与发行约定是否一致。",
        }
    )
    assert "募集资金用途核查" in text
    assert "募集资金 约定用途" in text
    assert "核验实际资金使用" in text


def test_catalog_attachment_filename_uses_suggested_name_and_disambiguates():
    record = {
        "document_id": "doc_1234567890abcdef",
        "source_filename": "001_source.pdf",
        "suggested_filename": "测试公司_年度报告_2025_doc_12345678.pdf",
    }
    assert (
        catalog_attachment_filename(record)
        == "测试公司_年度报告_2025_doc_12345678.pdf"
    )
    assert catalog_attachment_filename(
        record, {"测试公司_年度报告_2025_doc_12345678.pdf"}
    ) == "测试公司_年度报告_2025_doc_12345678_12345678.pdf"


def test_combined_score_uses_only_semantic_and_keyword_signals():
    scores = combine_retrieval_scores(
        np.array([0.2, 0.4, 0.6]),
        np.array([0.8, 0.3, 0.1]),
        semantic_weight=0.75,
        keyword_weight=0.25,
    )
    assert np.allclose(scores, [0.25, 0.4464286, 0.75])


def test_minmax_normalizes_scores():
    assert np.allclose(minmax(np.array([2.0, 4.0, 6.0])), [0.0, 0.5, 1.0])
