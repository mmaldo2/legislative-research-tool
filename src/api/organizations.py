"""Organization management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_api_key
from src.models.organization import Organization
from src.schemas.organization import OrgCreate, OrgResponse, OrgWithKeyResponse
from src.services.auth_service import AuthContext, create_organization

router = APIRouter()


@router.post("/orgs", response_model=OrgWithKeyResponse, status_code=201)
@limiter.limit("5/minute")
async def create_org(
    request: Request,
    body: OrgCreate,
    db: AsyncSession = Depends(get_session),
) -> OrgWithKeyResponse:
    """Create a new organization with an initial API key.

    The API key is returned in the response and cannot be retrieved again.
    """
    # Check slug uniqueness
    existing = await db.execute(select(Organization).where(Organization.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Organization slug already taken")

    org, full_key = await create_organization(db, name=body.name, slug=body.slug)

    return OrgWithKeyResponse(
        organization=OrgResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            plan=org.plan,
            created_at=org.created_at,
        ),
        api_key=full_key,
        key_hint=full_key[-4:],
    )


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> OrgResponse:
    """Get organization details. Requires auth and org membership."""
    if auth.tier != "dev" and auth.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized for this organization")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        plan=org.plan,
        created_at=org.created_at,
    )
