from datetime import date

from pydantic import BaseModel

from src.schemas.common import MetaResponse


class SessionResponse(BaseModel):
    id: str
    jurisdiction_id: str
    name: str
    identifier: str
    classification: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class SessionListResponse(BaseModel):
    data: list[SessionResponse]
    meta: MetaResponse
