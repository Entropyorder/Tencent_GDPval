import json

import numpy as np

from finance_forensics.retrieval import (
    build_document_text,
    catalog_attachment_filename,
    load_queries,
    minmax,
    profile_quality_relevance,
    retrieval_query_text,
    type_relevance,
)


def test_load_queries_accepts_query_only_records(tmp_path):
    path = tmp_path / "queries.json"
    path.write_text(
        json.dumps([{"query": "信用风险分析"}, {"query": "经营表现分析"}]),
        encoding="utf-8",
    )
    assert load_queries(path) == ["信用风险分析", "经营表现分析"]


def test_build_document_text_uses_profile_fields():
    text = build_document_text(
        {
            "document_type": "rating_report",
            "business_topic": "信用风险",
            "industry": "金融",
            "keywords": ["评级", "偿债"],
            "summary": "某份评级资料的摘要。",
        }
    )
    assert "信用评级报告" in text
    assert "信用风险" in text
    assert "评级 偿债" in text


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


def test_type_relevance_prefers_matching_document_type():
    query = "请完成目标企业的信用评级与风险分析，并考虑监管政策变化"
    assert type_relevance(query, "rating_report") == 1.0
    assert type_relevance(query, "rating_report") > type_relevance(
        query, "policy_document"
    )


def test_retrieval_query_reduces_generic_task_to_search_focus():
    focus = retrieval_query_text("请完成目标企业的经营与财务表现评估")
    assert "经营业绩" in focus
    assert len(focus) < 100


def test_profile_quality_penalizes_review_templates_for_enterprise_query():
    query = "分析目标企业的经营与财务表现"
    company = {
        "company_name": "测试公司",
        "subject_name": "测试公司",
        "needs_review": False,
    }
    template = {"needs_review": True}
    assert profile_quality_relevance(query, company) > profile_quality_relevance(
        query, template
    )


def test_minmax_normalizes_scores():
    assert np.allclose(minmax(np.array([2.0, 4.0, 6.0])), [0.0, 0.5, 1.0])
