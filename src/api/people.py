"""Legislator/person endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import escape_like, get_session
from src.models.person import Person
from src.schemas.common import MetaResponse

router = APIRouter()


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


@router.get("/people", response_model=PersonListResponse)
async def list_people(
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    party: str | None = Query(None, description="Filter by party"),
    chamber: str | None = Query(None, description="Filter by chamber (upper/lower)"),
    q: str | None = Query(None, description="Search by name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> PersonListResponse:
    """List legislators with optional filters."""
    stmt = select(Person)

    if jurisdiction:
        stmt = stmt.where(Person.current_jurisdiction_id == jurisdiction)
    if party:
        stmt = stmt.where(Person.party == party)
    if chamber:
        stmt = stmt.where(Person.current_chamber == chamber)
    if q:
        stmt = stmt.where(Person.name.ilike(f"%{escape_like(q)}%", escape="\\"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Person.name)
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    people = result.scalars().all()

    data = [
        PersonResponse(
            id=p.id,
            name=p.name,
            party=p.party,
            current_jurisdiction_id=p.current_jurisdiction_id,
            current_chamber=p.current_chamber,
            current_district=p.current_district,
        )
        for p in people
    ]

    return PersonListResponse(
        data=data,
        meta=MetaResponse(total_count=total, page=page, per_page=per_page),
    )


@router.get("/people/{person_id}", response_model=PersonResponse)
async def get_person(
    person_id: str,
    db: AsyncSession = Depends(get_session),
) -> PersonResponse:
    """Get a legislator by ID."""
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    return PersonResponse(
        id=person.id,
        name=person.name,
        party=person.party,
        current_jurisdiction_id=person.current_jurisdiction_id,
        current_chamber=person.current_chamber,
        current_district=person.current_district,
    )
