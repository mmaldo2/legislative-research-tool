"""Pydantic response models for committee hearings."""

from datetime import date, datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class HearingResponse(BaseModel):
    """Single committee hearing response."""

    id: str
    bill_id: str | None = None
    committee_name: str
    committee_code: str | None = None
    chamber: str | None = None
    title: str
    hearing_date: date | None = None
    location: str | None = None
    url: str | None = None
    congress: int | None = None
    created_at: datetime | None = None
    linked_bill_ids: list[str] = []


class HearingListResponse(BaseModel):
    """Paginated list of committee hearings."""

    data: list[HearingResponse]
    meta: MetaResponse
