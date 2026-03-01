"""Health check and ingestion status endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.bill import Bill
from src.models.ingestion_run import IngestionRun
from src.models.jurisdiction import Jurisdiction
from src.schemas.status import HealthResponse, IngestionRunResponse, StatusResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_session)) -> HealthResponse:
    """Health check — verifies API and database connectivity."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(status="ok", version="0.1.0", database=db_status)


@router.get("/status", response_model=StatusResponse)
async def ingestion_status(db: AsyncSession = Depends(get_session)) -> StatusResponse:
    """Ingestion status — bill counts and recent ingestion runs."""
    total_bills = (await db.execute(select(func.count(Bill.id)))).scalar_one()
    total_jurisdictions = (
        await db.execute(select(func.count(Jurisdiction.id)))
    ).scalar_one()

    runs_result = await db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(10)
    )
    runs = runs_result.scalars().all()

    recent_runs = [
        IngestionRunResponse(
            id=r.id,
            source=r.source,
            run_type=r.run_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            bills_created=r.bills_created,
            bills_updated=r.bills_updated,
        )
        for r in runs
    ]

    return StatusResponse(
        total_bills=total_bills,
        total_jurisdictions=total_jurisdictions,
        recent_runs=recent_runs,
    )
