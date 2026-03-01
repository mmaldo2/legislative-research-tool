from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str


class IngestionRunResponse(BaseModel):
    id: int
    source: str
    run_type: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records_created: int
    records_updated: int


class StatusResponse(BaseModel):
    total_bills: int
    total_jurisdictions: int
    recent_runs: list[IngestionRunResponse]
