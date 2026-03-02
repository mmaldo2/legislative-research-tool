"""Pydantic schemas for trend aggregation endpoints."""

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class TrendDataPoint(BaseModel):
    period: str = Field(description="ISO date string for the start of the time bucket")
    dimension: str = Field(description="Group-by dimension value (e.g., jurisdiction ID, topic)")
    count: int = Field(description="Number of items in this bucket")


class TrendTopicDataPoint(TrendDataPoint):
    share_pct: float = Field(description="Percentage share of total bills in this period")


class TrendMeta(MetaResponse):
    bucket: str = "month"
    group_by: str = "jurisdiction"
    date_from: str = ""
    date_to: str = ""


class TrendResponse(BaseModel):
    data: list[TrendDataPoint] = []
    meta: TrendMeta = TrendMeta()


class TrendTopicResponse(BaseModel):
    data: list[TrendTopicDataPoint] = []
    meta: TrendMeta = TrendMeta()


class TrendSummaryResponse(BaseModel):
    narrative: str = ""
    key_findings: list[str] = []
    period_covered: str = ""
    bills_analyzed: int = 0
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    ai_model: str | None = None
    ai_prompt_version: str | None = None
