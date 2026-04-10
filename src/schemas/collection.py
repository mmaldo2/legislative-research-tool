"""Pydantic schemas for research collections."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.schemas.common import MetaResponse


class CollectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class CollectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


class CollectionItemAdd(BaseModel):
    bill_id: str
    notes: str | None = Field(None, max_length=2000)


class CollectionItemUpdate(BaseModel):
    notes: str | None = Field(None, max_length=2000)


class CollectionItemResponse(BaseModel):
    id: int
    bill_id: str
    bill_identifier: str | None = None
    bill_title: str | None = None
    jurisdiction_id: str | None = None
    status: str | None = None
    notes: str | None = None
    added_at: datetime | None = None


class CollectionResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    item_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    items: list[CollectionItemResponse] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CollectionListResponse(BaseModel):
    data: list[CollectionResponse]
    meta: MetaResponse
