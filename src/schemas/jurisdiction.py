from pydantic import BaseModel

from src.schemas.common import MetaResponse


class JurisdictionResponse(BaseModel):
    id: str
    name: str
    classification: str
    abbreviation: str | None = None
    fips_code: str | None = None


class JurisdictionListResponse(BaseModel):
    data: list[JurisdictionResponse]
    meta: MetaResponse


class SessionBillCount(BaseModel):
    session_id: str
    session_name: str
    bill_count: int


class SubjectCount(BaseModel):
    subject: str
    count: int


class JurisdictionStatsResponse(BaseModel):
    total_bills: int
    total_legislators: int
    bills_by_status: dict[str, int]
    bills_by_session: list[SessionBillCount]
    top_subjects: list[SubjectCount]
