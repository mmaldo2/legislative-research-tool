from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class SummarizeRequest(BaseModel):
    bill_id: str


class ClassifyRequest(BaseModel):
    bill_id: str


class BillSummaryOutput(BaseModel):
    """Structured output for bill summarization — used as LLM output schema."""

    plain_english_summary: str
    key_provisions: list[str]
    affected_populations: list[str]
    changes_to_existing_law: list[str]
    fiscal_implications: str | None = None
    effective_date: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class TopicClassificationOutput(BaseModel):
    """Structured output for topic classification."""

    primary_topic: str
    secondary_topics: list[str]
    policy_area: str
    confidence: float = Field(ge=0.0, le=1.0)


class VersionDiffRequest(BaseModel):
    bill_id: str
    version_a_id: str | None = None  # None = first version
    version_b_id: str | None = None  # None = latest version


class ConstitutionalRequest(BaseModel):
    bill_id: str


class PatternDetectRequest(BaseModel):
    bill_id: str
    top_k: int = Field(default=5, ge=1, le=20)  # Number of similar bills to analyze


class VersionDiffChange(BaseModel):
    """A single change between two bill versions."""

    section: str
    change_type: Literal["added", "removed", "modified"]
    significance: Literal["major", "moderate", "minor"]
    before: str | None = None
    after: str | None = None
    description: str


class VersionDiffOutput(BaseModel):
    """Structured output for bill version diff analysis."""

    version_a_name: str
    version_b_name: str
    changes: list[VersionDiffChange]
    summary_of_changes: str
    direction_of_change: str  # e.g. "narrowed scope", "added enforcement"
    amendments_incorporated: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class ConstitutionalConcern(BaseModel):
    """A single constitutional concern flagged in a bill."""

    provision: str  # Which amendment/clause
    severity: Literal["high", "moderate", "low"]
    bill_section: str  # Which part of the bill
    description: str
    relevant_precedents: list[str]  # Case names


class ConstitutionalAnalysisOutput(BaseModel):
    """Structured output for constitutional flag analysis."""

    concerns: list[ConstitutionalConcern]
    preemption_issues: list[str]
    has_severability_clause: bool
    overall_risk_level: Literal["high", "moderate", "low", "minimal", "unknown"]
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class PatternBillInfo(BaseModel):
    """Info about one bill in a cross-jurisdictional pattern."""

    bill_id: str
    identifier: str
    jurisdiction_id: str
    title: str
    variations: list[str]  # How this bill differs from the source


class PatternDetectionOutput(BaseModel):
    """Structured output for cross-jurisdictional pattern detection."""

    pattern_type: Literal["identical", "adapted", "inspired", "coincidental", "unknown"]
    common_framework: str
    source_organization: str | None = None  # ALEC, NCSL, etc. if identifiable
    bills_analyzed: list[PatternBillInfo]
    shared_provisions: list[str]
    key_variations: list[str]
    model_legislation_confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class AnalysisResponse(BaseModel):
    """Read-only view of a stored AI analysis."""

    id: int
    bill_id: str
    analysis_type: str
    result: dict
    model_used: str
    prompt_version: str
    confidence: Decimal | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    cost_usd: Decimal | None = None
    created_at: datetime | None = None


class AnalysisListResponse(BaseModel):
    data: list[AnalysisResponse]
    meta: MetaResponse
