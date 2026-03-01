from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

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
    confidence: float


class TopicClassificationOutput(BaseModel):
    """Structured output for topic classification."""

    primary_topic: str
    secondary_topics: list[str]
    policy_area: str
    confidence: float


class BillComparisonOutput(BaseModel):
    """Structured output for comparing two bills or bill versions."""

    similarities: list[str]
    differences: list[str]
    key_changes: list[str]
    overall_assessment: str
    similarity_score: float


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
