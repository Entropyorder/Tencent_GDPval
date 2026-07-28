from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from finance_forensics.config import PROMPT_DIR
from finance_forensics.models import QueryDraft
from finance_forensics.query_llm import GDPvalQueryClient, normalize_query_payload
from finance_forensics.query_pipeline import QueryProcessor, task_id_for_document


def generic_query():
    return (
        "你是一名信用分析师，需要为内部决策机构准备目标企业的信用跟踪分析。"
        "请根据后续提供的相关参考文件，梳理企业在报告期内的业务发展、经营趋势"
        "和财务状况，从盈利能力、资产负债结构、现金流、偿债能力、业务集中度"
        "及外部支持等维度识别重要变化。对可比期间数据进行必要的增减变动和比率"
        "计算，区分材料披露的事实、计算结果与专业判断，并说明异常变化可能反映"
        "的风险。形成一份结构清晰、可复核的分析工作底稿，包含核心指标对比、"
        "业务与财务分析、主要风险及后续监控建议。所有数据和结论必须能够追溯到"
        "所提供材料，计算过程应保留公式或口径说明；资料不足或口径不一致之处"
        "应明确标记，不得自行补造数据或引入无法验证的结论。"
        "在材料允许的范围内比较不同期间或不同业务板块的变化，解释关键驱动因素，"
        "并说明判断所依赖的证据。最终成果应便于管理层快速识别值得进一步核查的"
        "事项，同时为后续补充资料、更新分析和持续监控保留清晰结构，并清楚呈现"
        "关键假设、分析口径以及尚待验证的问题。"
    )


def test_query_payload_only_keeps_query():
    normalized = normalize_query_payload(
        {"query": f"  {generic_query()}  ", "rubric_items": ["not allowed"]}
    )
    assert normalized == {"query": generic_query()}
    assert QueryDraft.model_validate(normalized).query == generic_query()


def test_query_only_has_a_600_character_upper_limit():
    assert QueryDraft(query="简短但完整的职业任务。").query == "简短但完整的职业任务。"
    assert QueryDraft(query="任" * 600).query == "任" * 600
    with pytest.raises(ValidationError):
        QueryDraft(query="任" * 601)


def test_task_id_is_stable_and_prompt_version_specific():
    first = task_id_for_document("doc_1234", "v1")
    assert first == task_id_for_document("doc_1234", "v1")
    assert first != task_id_for_document("doc_1234", "v2")


def test_user_prompt_contains_schema_context_and_document():
    client = GDPvalQueryClient.__new__(GDPvalQueryClient)
    client.settings = SimpleNamespace(max_input_chars=100)
    client.user_prompt_template = (
        PROMPT_DIR / "通用查询输入模板.md"
    ).read_text(encoding="utf-8")
    result = client.build_user_prompt(
        {
            "document_type": "rating_report",
            "variation_marker": "a1b2c3d4",
            "forbidden_specific_terms": ["某公司"],
        },
        "这是一段具有区分度的样本文本。",
    )
    assert "必需的 JSON Schema" in result
    assert '"query"' in result
    assert "rating_report" in result
    assert "a1b2c3d4" in result
    assert "这是一段具有区分度的样本文本。" in result
    assert "某公司" not in result


def test_query_processor_passes_extracted_document_text(tmp_path):
    source = tmp_path / "sample.csv"
    source.write_text("主题,内容\n独特样本,待核验的事项\n", encoding="utf-8")

    class CapturingClient:
        prompt_version = "gdpval_query_v3"

        def __init__(self):
            self.document_content = None

        def generate(self, context, document_content):
            self.document_content = document_content
            return QueryDraft(query="核验材料间的关键事实冲突并形成处置意见。")

    client = CapturingClient()
    settings = SimpleNamespace(max_input_chars=1000, model="test-model")
    processor = QueryProcessor(
        settings,
        client,
        {
            source.name: {
                "document_id": "doc_1234",
                "document_type": "other",
            }
        },
    )

    record = processor.process(source)

    assert record.generation.status == "success"
    assert "独特样本" in client.document_content
    assert "待核验的事项" in client.document_content
