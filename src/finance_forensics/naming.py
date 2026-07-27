from pathlib import Path
import re

from .models import LLMProfile


DOCUMENT_TYPE_LABELS = {
    "annual_report": "年度报告",
    "prospectus": "公开说明书",
    "audit_report": "审计报告",
    "financial_statement": "财务报表",
    "rating_report": "评级报告",
    "regulatory_inquiry": "监管问询函",
    "regulatory_reply": "监管回复",
    "legal_opinion": "法律意见书",
    "bond_report": "债券报告",
    "offering_document": "募集说明书",
    "statistical_data": "统计数据",
    "business_data": "业务数据",
    "research_report": "研究报告",
    "policy_document": "政策文件",
    "other": "其他文件",
}


def normalize_summary(value, max_chars=500):
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def sanitize_component(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value or "")
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip(" ._")


def normalize_filename(candidate, source_path, document_id, profile):
    extension = source_path.suffix.lower()
    candidate_stem = Path(candidate or "").stem
    subject = profile.company_name or profile.subject_name or "主体待确认"
    topic = profile.business_topic or candidate_stem or "内容待确认"
    doc_type = DOCUMENT_TYPE_LABELS.get(profile.document_type, "其他文件")
    period = profile.reporting_period or profile.publish_date or "期间待确认"
    raw_stem = "_".join((subject, topic, doc_type, period))

    stem = sanitize_component(raw_stem)
    short_id = document_id[:12]
    if short_id not in stem:
        stem = f"{stem}_{short_id}"
    max_stem_length = max(20, 180 - len(extension))
    stem = stem[:max_stem_length].rstrip(" ._")
    return f"{stem}{extension}"


def profile_to_record_fields(profile: LLMProfile):
    return {
        "summary": normalize_summary(profile.summary),
        "subject_name": profile.subject_name,
        "company_name": profile.company_name,
        "business_topic": profile.business_topic,
        "document_type": profile.document_type,
        "reporting_period": profile.reporting_period,
        "publish_date": profile.publish_date,
        "industry": profile.industry,
        "security_code": profile.security_code,
        "market": profile.market,
        "keywords": list(dict.fromkeys(profile.keywords))[:8],
        "confidence": profile.confidence,
        "needs_review": profile.needs_review,
        "review_reasons": profile.review_reasons,
    }
