"""Pydantic schemas for trend aggregation endpoints."""

from pydantic import BaseModel, Field


class TrendDataPoint(BaseModel):
    period: str = Field(description="ISO date string for the start of the time bucket")
    dimension: str = Field(description="Group-by dimension value (e.g., jurisdiction ID, topic)")
    count: int = Field(description="Number of items in this bucket")


class TrendTopicDataPoint(TrendDataPoint):
    share_pct: float = Field(description="Percentage share of total bills in this period")


class TrendMeta(BaseModel):
    sources: list[str] = []
    last_updated: str | None = None
    total_count: int = 0
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
    confidence: float = 0.0
