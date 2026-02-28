from pydantic import BaseModel

from src.schemas.common import MetaResponse


class SearchRequest(BaseModel):
    q: str
    jurisdiction: str | None = None
    session: str | None = None
    mode: str = "hybrid"  # keyword, semantic, hybrid
    page: int = 1
    per_page: int = 20


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
