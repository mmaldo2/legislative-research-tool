"""Pydantic schemas for API key management."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class APIKeyResponse(BaseModel):
    """API key metadata — never exposes the full key."""

    id: uuid.UUID
    name: str
    prefix: str
    key_hint: str
    is_active: bool
    last_used_at: datetime | None = None
    request_count: int = 0
    created_at: datetime | None = None


class APIKeyCreatedResponse(BaseModel):
    """Returned on key creation — includes the full key (shown only once)."""

    id: uuid.UUID
    name: str
    api_key: str = Field(description="Full API key — shown only once, store it securely")
    key_hint: str
    created_at: datetime | None = None
