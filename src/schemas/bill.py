from datetime import date, datetime

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class BillSummary(BaseModel):
    id: str
    jurisdiction_id: str
    session_id: str
    identifier: str
    title: str
    status: str | None = None
    status_date: date | None = None
    introduced_date: date | None = None
    classification: list[str] | None = None
    subject: list[str] | None = None


class BillTextResponse(BaseModel):
    id: str
    version_name: str
    version_date: date | None = None
    content_text: str | None = None
    source_url: str | None = None
    word_count: int | None = None


class BillActionResponse(BaseModel):
    action_date: date
    description: str
    classification: list[str] | None = None
    chamber: str | None = None


class SponsorResponse(BaseModel):
    person_id: str
    name: str
    party: str | None = None
    classification: str  # primary, cosponsor


class BillDetailResponse(BaseModel):
    id: str
    jurisdiction_id: str
    session_id: str
    identifier: str
    title: str
    status: str | None = None
    status_date: date | None = None
    introduced_date: date | None = None
    classification: list[str] | None = None
    subject: list[str] | None = None
    source_urls: list | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    ai_summary: dict | None = None
    texts: list[BillTextResponse] = []
    actions: list[BillActionResponse] = []
    sponsors: list[SponsorResponse] = []


class BillListResponse(BaseModel):
    data: list[BillSummary]
    meta: MetaResponse
