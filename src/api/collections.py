"""Research collections CRUD endpoints — curate and organize bills."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import get_session, limiter
from src.models.bill import Bill
from src.models.collection import Collection, CollectionItem
from src.schemas.collection import (
    CollectionCreate,
    CollectionDetailResponse,
    CollectionItemAdd,
    CollectionItemResponse,
    CollectionItemUpdate,
    CollectionListResponse,
    CollectionResponse,
    CollectionUpdate,
)
from src.schemas.common import MetaResponse

router = APIRouter()


def get_client_id(x_client_id: str | None = Header(None)) -> str:
    """Get client ID from header or return 'anonymous'."""
    return x_client_id or "anonymous"


async def _get_collection_or_404(
    db: AsyncSession,
    collection_id: int,
    client_id: str,
    *,
    load_items: bool = False,
) -> Collection:
    """Fetch a collection by ID, enforcing ownership. Raises 404 or 403."""
    stmt = select(Collection).where(Collection.id == collection_id)
    if load_items:
        stmt = stmt.options(selectinload(Collection.items))
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    if collection.client_id != client_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this collection")
    return collection


@router.post("/collections", response_model=CollectionResponse, status_code=201)
@limiter.limit("30/minute")
async def create_collection(
    request: Request,
    body: CollectionCreate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> CollectionResponse:
    """Create a new research collection."""
    collection = Collection(
        client_id=client_id,
        name=body.name,
        description=body.description,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        item_count=0,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.get("/collections", response_model=CollectionListResponse)
async def list_collections(
    client_id: str = Depends(get_client_id),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> CollectionListResponse:
    """List collections for the current client with pagination."""
    base_stmt = select(Collection).where(Collection.client_id == client_id)

    # Total count
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated results with item counts via subquery
    item_count_subq = (
        select(
            CollectionItem.collection_id,
            func.count(CollectionItem.id).label("item_count"),
        )
        .group_by(CollectionItem.collection_id)
        .subquery()
    )

    stmt = (
        select(Collection, func.coalesce(item_count_subq.c.item_count, 0).label("item_count"))
        .outerjoin(item_count_subq, Collection.id == item_count_subq.c.collection_id)
        .where(Collection.client_id == client_id)
        .order_by(Collection.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    rows = result.all()

    data = [
        CollectionResponse(
            id=col.id,
            name=col.name,
            description=col.description,
            item_count=item_count,
            created_at=col.created_at,
            updated_at=col.updated_at,
        )
        for col, item_count in rows
    ]

    return CollectionListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total,
            page=page,
            per_page=per_page,
        ),
    )


@router.get("/collections/{collection_id}", response_model=CollectionDetailResponse)
async def get_collection(
    collection_id: int,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> CollectionDetailResponse:
    """Get a collection with all its items."""
    collection = await _get_collection_or_404(db, collection_id, client_id, load_items=True)

    items = [
        CollectionItemResponse(
            id=item.id,
            bill_id=item.bill_id,
            notes=item.notes,
            added_at=item.added_at,
        )
        for item in collection.items
    ]

    return CollectionDetailResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        items=items,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.patch("/collections/{collection_id}", response_model=CollectionResponse)
@limiter.limit("30/minute")
async def update_collection(
    request: Request,
    collection_id: int,
    body: CollectionUpdate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> CollectionResponse:
    """Update a collection's name and/or description."""
    collection = await _get_collection_or_404(db, collection_id, client_id, load_items=True)

    if body.name is not None:
        collection.name = body.name
    if body.description is not None:
        collection.description = body.description

    await db.commit()
    await db.refresh(collection)

    item_count = len(collection.items)

    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        item_count=item_count,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


@router.delete("/collections/{collection_id}", status_code=204)
@limiter.limit("30/minute")
async def delete_collection(
    request: Request,
    collection_id: int,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Delete a collection and all its items."""
    collection = await _get_collection_or_404(db, collection_id, client_id)
    await db.delete(collection)
    await db.commit()


@router.post(
    "/collections/{collection_id}/items",
    response_model=CollectionItemResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def add_item(
    request: Request,
    collection_id: int,
    body: CollectionItemAdd,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> CollectionItemResponse:
    """Add a bill to a collection."""
    await _get_collection_or_404(db, collection_id, client_id)

    # Verify the bill exists
    bill_result = await db.execute(select(Bill).where(Bill.id == body.bill_id))
    if not bill_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Bill not found")

    # Check for duplicate
    dup_stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.bill_id == body.bill_id,
    )
    existing = (await db.execute(dup_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Bill already in collection")

    item = CollectionItem(
        collection_id=collection_id,
        bill_id=body.bill_id,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return CollectionItemResponse(
        id=item.id,
        bill_id=item.bill_id,
        notes=item.notes,
        added_at=item.added_at,
    )


@router.delete("/collections/{collection_id}/items/{bill_id}", status_code=204)
@limiter.limit("30/minute")
async def remove_item(
    request: Request,
    collection_id: int,
    bill_id: str,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> None:
    """Remove a bill from a collection."""
    await _get_collection_or_404(db, collection_id, client_id)

    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.bill_id == bill_id,
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in collection")

    await db.delete(item)
    await db.commit()


@router.patch(
    "/collections/{collection_id}/items/{bill_id}",
    response_model=CollectionItemResponse,
)
@limiter.limit("30/minute")
async def update_item_notes(
    request: Request,
    collection_id: int,
    bill_id: str,
    body: CollectionItemUpdate,
    client_id: str = Depends(get_client_id),
    db: AsyncSession = Depends(get_session),
) -> CollectionItemResponse:
    """Update notes on a collection item."""
    await _get_collection_or_404(db, collection_id, client_id)

    stmt = select(CollectionItem).where(
        CollectionItem.collection_id == collection_id,
        CollectionItem.bill_id == bill_id,
    )
    item = (await db.execute(stmt)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in collection")

    if body.notes is not None:
        item.notes = body.notes

    await db.commit()
    await db.refresh(item)

    return CollectionItemResponse(
        id=item.id,
        bill_id=item.bill_id,
        notes=item.notes,
        added_at=item.added_at,
    )
