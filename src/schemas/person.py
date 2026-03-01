from datetime import date

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class PersonResponse(BaseModel):
    id: str
    name: str
    party: str | None = None
    current_jurisdiction_id: str | None = None
    current_chamber: str | None = None
    current_district: str | None = None
    image_url: str | None = None


class PersonListResponse(BaseModel):
    data: list[PersonResponse]
    meta: MetaResponse


class PersonVoteResponse(BaseModel):
    vote_event_id: str
    bill_id: str
    bill_identifier: str
    bill_title: str
    vote_date: date | None = None
    chamber: str | None = None
    motion_text: str | None = None
    result: str | None = None
    option: str


class PersonVoteListResponse(BaseModel):
    data: list[PersonVoteResponse]
    meta: MetaResponse


class PersonStatsResponse(BaseModel):
    bills_sponsored: int
    bills_cosponsored: int
    votes_cast: int
    vote_participation_rate: float | None = None
