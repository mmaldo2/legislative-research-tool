from datetime import date

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class VoteRecordResponse(BaseModel):
    person_id: str
    person_name: str | None = None
    option: str  # yes, no, absent, etc.


class VoteEventResponse(BaseModel):
    id: str
    bill_id: str
    vote_date: date | None = None
    chamber: str | None = None
    motion_text: str | None = None
    result: str | None = None
    yes_count: int | None = None
    no_count: int | None = None
    other_count: int | None = None
    records: list[VoteRecordResponse] = []


class VoteEventListResponse(BaseModel):
    data: list[VoteEventResponse]
    meta: MetaResponse
