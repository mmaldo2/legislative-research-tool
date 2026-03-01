from datetime import UTC, datetime
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


class DiffusionEvent(BaseModel):
    """A single instance of a bill appearing in a jurisdiction."""

    bill_id: str
    identifier: str
    jurisdiction_id: str
    title: str
    status: str | None = None
    status_date: str | None = None
    similarity_score: float = Field(ge=0.0, le=1.0)


class DiffusionOutput(BaseModel):
    """Tracks how a legislative idea spread across jurisdictions over time."""

    source_bill_id: str
    source_identifier: str
    source_jurisdiction: str
    source_date: str | None = None
    timeline: list[DiffusionEvent]
    total_jurisdictions: int
    earliest_date: str | None = None
    latest_date: str | None = None
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


class PredictRequest(BaseModel):
    bill_id: str


class PredictionFactor(BaseModel):
    """A factor influencing the prediction."""

    factor: str
    direction: Literal["positive", "negative", "neutral"]
    weight: Literal["high", "moderate", "low"]
    explanation: str


class PredictionOutput(BaseModel):
    """Structured output for bill outcome prediction."""

    predicted_outcome: Literal["pass", "fail", "stall", "uncertain"]
    confidence: float = Field(ge=0.0, le=1.0)
    passage_probability: float = Field(ge=0.0, le=1.0)
    key_factors: list[PredictionFactor]
    historical_comparison: str
    summary: str


class ReportRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    jurisdiction: str | None = None
    max_bills: int = Field(default=20, ge=1, le=50)


class ReportSection(BaseModel):
    """A section of a generated research report."""

    heading: str
    content: str


class ReportOutput(BaseModel):
    """Structured output for an automated research report."""

    title: str
    executive_summary: str
    sections: list[ReportSection]
    bills_analyzed: int
    jurisdictions_covered: list[str]
    key_findings: list[str]
    trends: list[str]
    generated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
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
