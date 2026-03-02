"""API key management endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_api_key
from src.models.api_key import APIKey
from src.models.organization import Organization
from src.schemas.api_key import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse
from src.services.auth_service import AuthContext, provision_api_key

router = APIRouter()


def _require_org_access(auth: AuthContext, org_id: uuid.UUID) -> None:
    """Verify the caller belongs to the target organization."""
    if auth.tier != "dev" and auth.org_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized for this organization")


@router.post(
    "/orgs/{org_id}/api-keys",
    response_model=APIKeyCreatedResponse,
    status_code=201,
)
@limiter.limit("10/minute")
async def create_api_key(
    request: Request,
    org_id: uuid.UUID,
    body: APIKeyCreate,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> APIKeyCreatedResponse:
    """Provision a new API key for an organization.

    The full key is returned only once — store it securely.
    """
    _require_org_access(auth, org_id)

    # Verify org exists
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    key_record, full_key = await provision_api_key(db, org_id=org_id, name=body.name)

    return APIKeyCreatedResponse(
        id=key_record.id,
        name=key_record.name,
        api_key=full_key,
        key_hint=key_record.key_hint,
        created_at=key_record.created_at,
    )


@router.get("/orgs/{org_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    org_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> list[APIKeyResponse]:
    """List all API keys for an organization (hints only, never full keys)."""
    _require_org_access(auth, org_id)

    result = await db.execute(
        select(APIKey).where(APIKey.org_id == org_id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        APIKeyResponse(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            key_hint=k.key_hint,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            request_count=k.request_count,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/orgs/{org_id}/api-keys/{key_id}", status_code=204)
@limiter.limit("10/minute")
async def revoke_api_key(
    request: Request,
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    auth: AuthContext = Depends(require_api_key),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Revoke an API key (soft delete — marks as inactive)."""
    _require_org_access(auth, org_id)

    result = await db.execute(select(APIKey).where(APIKey.id == key_id, APIKey.org_id == org_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    key.is_active = False
    await db.commit()
