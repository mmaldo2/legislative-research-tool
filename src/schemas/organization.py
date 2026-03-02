"""Pydantic schemas for organizations."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime | None = None


class OrgWithKeyResponse(BaseModel):
    """Returned on org creation — includes the initial API key (shown once)."""

    organization: OrgResponse
    api_key: str = Field(description="Full API key — shown only once, store it securely")
    key_hint: str = Field(description="Last 4 characters for identification")
