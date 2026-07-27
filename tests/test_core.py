import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from finance_forensics.extractors import (
    extract_doc,
    extract_spreadsheet_with_calamine,
    sample_text,
)
from finance_forensics.llm import extract_json_object, normalize_model_payload
from finance_forensics.metadata import CollectorMetadata
from finance_forensics.models import LLMProfile
from finance_forensics.naming import normalize_filename, normalize_summary


def profile(**overrides):
    values = {
        "subject_name": "测试公司股份有限公司",
        "company_name": "测试公司股份有限公司",
        "business_topic": "融资租赁业务经营情况",
        "document_type": "annual_report",
        "reporting_period": "2024年",
        "publish_date": "2025-04-01",
        "industry": "融资租赁",
        "security_code": None,
        "market": None,
        "summary": "测试摘要",
        "keywords": ["融资租赁"],
        "confidence": 0.9,
        "needs_review": False,
        "review_reasons": [],
        "suggested_filename": "测试公司_融资租赁业务_年度报告_2024年.pdf",
    }
    values.update(overrides)
    return LLMProfile(**values)


def test_summary_is_hard_limited():
    assert len(normalize_summary("字" * 550)) == 500


def test_filename_preserves_extension_and_adds_id():
    result = normalize_filename(
        '测试公司/融资租赁:"年报".xlsx',
        Path("source.pdf"),
        "doc_a13f99213fd1b280",
        profile(),
    )
    assert result.endswith(".pdf")
    assert "doc_a13f9921" in result
    assert "融资租赁业务经营情况" in result
    assert "年度报告" in result
    assert "2024年" in result
    assert "/" not in result
    assert ":" not in result


def test_sample_text_respects_limit():
    sampled, truncated = sample_text("abcdef" * 1000, 500)
    assert truncated is True
    assert len(sampled) <= 500


def test_collector_metadata_uses_download_index(tmp_path):
    path = tmp_path / "metadata.json"
    path.write_text(
        json.dumps([{"url": "https://first"}, {"url": "https://second"}]),
        encoding="utf-8",
    )
    metadata = CollectorMetadata.load(path)
    assert metadata.for_file("0002_report.pdf")["url"] == "https://second"


def test_json_response_parsing_and_normalization():
    payload = extract_json_object(
        '```json\n{"summary":"' + ("字" * 550) + '","keywords":["a","b"]}\n```'
    )
    normalized = normalize_model_payload(payload)
    assert len(normalized["summary"]) == 500
    assert normalized["keywords"] == ["a", "b"]


def test_spreadsheet_fallback_uses_calamine(tmp_path):
    workbook = MagicMock()
    workbook.sheet_names = ["财务数据"]
    sheet = MagicMock()
    sheet.iter_rows.return_value = iter([["项目", "金额"], ["收入", 123]])
    workbook.get_sheet_by_name.return_value = sheet
    with patch(
        "finance_forensics.extractors.CalamineWorkbook.from_path",
        return_value=workbook,
    ):
        result = extract_spreadsheet_with_calamine(
            tmp_path / "broken.xlsx", 30000, ValueError("invalid XML")
        )
    assert result.method == "python-calamine"
    assert "收入\t123" in result.text
    assert result.warnings


def test_doc_falls_back_to_catdoc(tmp_path):
    path = tmp_path / "wps.doc"
    path.write_bytes(b"fake")
    antiword_result = MagicMock(returncode=1, stdout=b"", stderr=b"not a Word Document")
    catdoc_result = MagicMock(
        returncode=0,
        stdout="测试公司年度财务报告".encode(),
        stderr=b"",
    )
    with (
        patch("finance_forensics.extractors.antiword_binary", return_value="antiword"),
        patch("finance_forensics.extractors.catdoc_binary", return_value="catdoc"),
        patch(
            "finance_forensics.extractors.subprocess.run",
            side_effect=[antiword_result, catdoc_result],
        ),
    ):
        result = extract_doc(path, 30000)
    assert result.method == "catdoc"
    assert "测试公司" in result.text
