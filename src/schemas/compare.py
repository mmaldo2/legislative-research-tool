from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class CompareRequest(BaseModel):
    """Request body for comparing two bills via LLM analysis."""

    bill_id_a: str
    bill_id_b: str


class SimilarBillResult(BaseModel):
    """A single bill returned from a similarity search."""

    bill_id: str
    identifier: str
    title: str
    jurisdiction_id: str
    status: str | None = None
    similarity_score: float


class SimilarBillsResponse(BaseModel):
    """Response wrapper for the similar-bills endpoint."""

    data: list[SimilarBillResult]
    meta: MetaResponse


class BillComparisonOutput(BaseModel):
    """Structured output for bill comparison — used as LLM output schema."""

    shared_provisions: list[str]
    unique_to_a: list[str]
    unique_to_b: list[str]
    key_differences: list[str]
    overall_assessment: str
    similarity_score: float  # 0.0-1.0
    is_model_legislation: bool
    confidence: float = Field(ge=0.0, le=1.0)
