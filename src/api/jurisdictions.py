"""Jurisdiction and legislative session endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.jurisdiction import Jurisdiction
from src.models.session import LegislativeSession
from src.schemas.common import MetaResponse
from src.schemas.jurisdiction import JurisdictionListResponse, JurisdictionResponse
from src.schemas.session import SessionListResponse, SessionResponse

router = APIRouter()


@router.get("/jurisdictions", response_model=JurisdictionListResponse)
async def list_jurisdictions(
    classification: str | None = Query(
        None, description="Filter by type (state, country, territory)"
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> JurisdictionListResponse:
    """List all available jurisdictions."""
    stmt = select(Jurisdiction)
    if classification:
        stmt = stmt.where(Jurisdiction.classification == classification)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Jurisdiction.name)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    jurisdictions = result.scalars().all()

    data = [
        JurisdictionResponse(
            id=j.id,
            name=j.name,
            classification=j.classification,
            abbreviation=j.abbreviation,
            fips_code=j.fips_code,
        )
        for j in jurisdictions
    ]

    return JurisdictionListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_session),
) -> SessionListResponse:
    """List legislative sessions, optionally filtered by jurisdiction."""
    stmt = select(LegislativeSession)
    if jurisdiction:
        stmt = stmt.where(LegislativeSession.jurisdiction_id == jurisdiction)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(LegislativeSession.start_date.desc().nullslast())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    data = [
        SessionResponse(
            id=s.id,
            jurisdiction_id=s.jurisdiction_id,
            name=s.name,
            identifier=s.identifier,
            classification=s.classification,
            start_date=s.start_date,
            end_date=s.end_date,
        )
        for s in sessions
    ]

    return SessionListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )
