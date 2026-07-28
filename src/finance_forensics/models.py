from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DocumentType = Literal[
    "annual_report",
    "prospectus",
    "audit_report",
    "financial_statement",
    "rating_report",
    "regulatory_inquiry",
    "regulatory_reply",
    "legal_opinion",
    "bond_report",
    "offering_document",
    "statistical_data",
    "business_data",
    "research_report",
    "policy_document",
    "other",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LLMProfile(StrictModel):
    subject_name: str | None = None
    company_name: str | None = None
    business_topic: str | None = None
    document_type: DocumentType = "other"
    reporting_period: str | None = None
    publish_date: str | None = None
    industry: str | None = None
    security_code: str | None = None
    market: str | None = None
    summary: str = Field(min_length=1, max_length=500)
    keywords: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list, max_length=8)
    suggested_filename: str = Field(min_length=1, max_length=240)


class SourceDetails(StrictModel):
    absolute_path: str
    extension: str
    size_bytes: int = Field(ge=0)
    sha256: str
    crawler_url: str | None = None
    crawler_title: str | None = None
    crawler_query: str | None = None
    search_index: int | None = None
    search_index_one_based: int | None = None
    collected_at: str | None = None


class ExtractionDetails(StrictModel):
    status: Literal["success", "failed"]
    method: str
    characters: int = Field(ge=0)
    total_units: int | None = Field(default=None, ge=0)
    units_read: int | None = Field(default=None, ge=0)
    truncated: bool = False
    encoding: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RenamingDetails(StrictModel):
    llm_suggested_filename: str | None = None
    normalized_filename: str | None = None
    applied: bool = False


class ProcessingDetails(StrictModel):
    status: Literal["success", "failed"]
    model: str
    prompt_version: str
    processed_at: str
    duration_seconds: float = Field(ge=0)
    error: str | None = None


class DocumentRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    document_id: str
    source_filename: str
    suggested_filename: str | None = None
    summary: str | None = Field(default=None, max_length=500)
    subject_name: str | None = None
    company_name: str | None = None
    business_topic: str | None = None
    document_type: DocumentType | None = None
    reporting_period: str | None = None
    publish_date: str | None = None
    industry: str | None = None
    security_code: str | None = None
    market: str | None = None
    keywords: list[str] = Field(default_factory=list, max_length=8)
    confidence: float | None = Field(default=None, ge=0, le=1)
    needs_review: bool = True
    review_reasons: list[str] = Field(default_factory=list)
    source: SourceDetails
    extraction: ExtractionDetails
    renaming: RenamingDetails
    processing: ProcessingDetails


class QueryDraft(StrictModel):
    query: str = Field(max_length=600)


class QueryGenerationDetails(StrictModel):
    status: Literal["success", "failed"]
    model: str
    prompt_version: str
    processed_at: str
    duration_seconds: float = Field(ge=0)
    error: str | None = None


class QueryRecord(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    task_id: str
    query: str | None = Field(default=None, max_length=600)
    source_document_id: str
    source_filename: str
    generation: QueryGenerationDetails
