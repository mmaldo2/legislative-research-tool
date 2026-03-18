"""Pydantic schemas for bill outcome prediction responses."""

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class PredictionFactor(BaseModel):
    """A feature contributing to the prediction."""

    feature: str
    value: float
    impact: str  # "positive" or "negative"


class PredictionResponse(BaseModel):
    """Response for GET /bills/{bill_id}/prediction."""

    bill_id: str
    committee_passage_probability: float = Field(ge=0.0, le=1.0)
    model_version: str
    key_factors: list[PredictionFactor]
    base_rate: float = Field(ge=0.0, le=1.0)
    meta: MetaResponse
