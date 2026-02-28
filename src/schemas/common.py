from pydantic import BaseModel


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 20


class MetaResponse(BaseModel):
    sources: list[str] = []
    last_updated: str | None = None
    ai_enriched: bool = False
    ai_model: str | None = None
    ai_prompt_version: str | None = None
    total_count: int | None = None
    page: int | None = None
    per_page: int | None = None
