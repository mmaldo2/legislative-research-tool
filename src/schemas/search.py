from pydantic import BaseModel

from src.schemas.common import MetaResponse


class SearchResult(BaseModel):
    bill_id: str
    identifier: str
    title: str
    jurisdiction_id: str
    status: str | None = None
    score: float
    snippet: str | None = None


class SearchResponse(BaseModel):
    data: list[SearchResult]
    meta: MetaResponse
