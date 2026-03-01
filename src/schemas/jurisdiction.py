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
