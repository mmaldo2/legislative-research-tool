"""Pydantic schemas for CRS report API responses."""

from datetime import date, datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class CrsReportResponse(BaseModel):
    """Single CRS report detail."""

    id: str
    title: str
    summary: str | None = None
    authors: list[str] | None = None
    topics: list[str] | None = None
    publication_date: date | None = None
    most_recent_date: date | None = None
    source_url: str | None = None
    pdf_url: str | None = None
    related_bill_ids: list[str] | None = None
    content_text: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CrsReportListResponse(BaseModel):
    """Paginated list of CRS reports."""

    data: list[CrsReportResponse]
    meta: MetaResponse
