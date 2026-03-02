"""Authentication service — API key generation and verification."""

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.api_key import APIKey
from src.models.organization import Organization


@dataclass
class AuthContext:
    """Resolved identity context for the current request."""

    org_id: uuid.UUID | None
    tier: str  # "dev", "free", "pro", "enterprise"


def generate_api_key(prefix: str = "sk_live_") -> tuple[str, str, str]:
    """Generate an API key.

    Returns (full_key, key_hint, key_hash). full_key is shown once to the user.
    """
    random_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}{random_part}"
    key_hint = full_key[-4:]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hint, key_hash


def hash_api_key(raw_key: str) -> str:
    """Hash an API key with SHA-256 for lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "org"


async def create_organization(
    session: AsyncSession,
    *,
    name: str,
    slug: str,
    plan: str = "free",
) -> tuple[Organization, str]:
    """Create an organization and its first API key.

    Returns (organization, full_api_key). The full key is shown only once.
    """
    org = Organization(name=name, slug=slug, plan=plan)
    session.add(org)
    await session.flush()  # Get org.id

    full_key, key_hint, key_hash = generate_api_key()
    api_key = APIKey(
        org_id=org.id,
        name="Default",
        key_hash=key_hash,
        key_hint=key_hint,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(org)
    return org, full_key


async def provision_api_key(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    name: str,
) -> tuple[APIKey, str]:
    """Provision a new API key for an organization.

    Returns (api_key_record, full_api_key). The full key is shown only once.
    """
    full_key, key_hint, key_hash = generate_api_key()
    api_key = APIKey(
        org_id=org_id,
        name=name,
        key_hash=key_hash,
        key_hint=key_hint,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, full_key


async def verify_api_key(session: AsyncSession, raw_key: str) -> AuthContext | None:
    """Verify an API key and return the auth context, or None if invalid."""
    key_hash = hash_api_key(raw_key)
    result = await session.execute(
        select(APIKey)
        .options(selectinload(APIKey.organization))
        .where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
    )
    key = result.scalar_one_or_none()
    if not key:
        return None

    # Check expiration
    if key.expires_at and key.expires_at < datetime.now(UTC):
        return None

    # Update usage stats
    key.last_used_at = datetime.now(UTC)
    key.request_count += 1
    await session.commit()

    return AuthContext(org_id=key.org_id, tier=key.organization.plan)
