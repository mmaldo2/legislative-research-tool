from pydantic import BaseModel

from src.schemas.common import MetaResponse


class PersonResponse(BaseModel):
    id: str
    name: str
    party: str | None = None
    current_jurisdiction_id: str | None = None
    current_chamber: str | None = None
    current_district: str | None = None


class PersonListResponse(BaseModel):
    data: list[PersonResponse]
    meta: MetaResponse
