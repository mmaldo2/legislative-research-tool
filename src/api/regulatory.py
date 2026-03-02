"""Federal Register regulatory document endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String as SAString
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session
from src.models.regulatory_document import RegulatoryDocument
from src.schemas.common import MetaResponse
from src.schemas.regulatory import RegulatoryDocumentListResponse, RegulatoryDocumentResponse

router = APIRouter()


@router.get("/regulatory", response_model=RegulatoryDocumentListResponse)
async def list_regulatory_documents(
    document_type: str | None = Query(
        None,
        description="Filter by type: rule, proposed_rule, notice, presidential_document",
    ),
    agency: str | None = Query(
        None, description="Filter by agency name (case-insensitive substring match)"
    ),
    date_from: date | None = Query(None, description="Start of publication date range (inclusive)"),
    date_to: date | None = Query(None, description="End of publication date range (inclusive)"),
    related_bill: str | None = Query(
        None, description="Filter by related bill reference (e.g. 'HR 1234')"
    ),
    q: str | None = Query(None, description="Search title (case-insensitive contains)"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_session),
) -> RegulatoryDocumentListResponse:
    """List Federal Register regulatory documents with optional filters."""
    query = select(RegulatoryDocument)
    count_query = select(func.count(RegulatoryDocument.id))

    if document_type:
        query = query.where(RegulatoryDocument.document_type == document_type)
        count_query = count_query.where(RegulatoryDocument.document_type == document_type)

    if agency:
        # Cast JSONB to text for case-insensitive substring matching
        agency_filter = func.cast(RegulatoryDocument.agency_names, SAString).ilike(f"%{agency}%")
        query = query.where(agency_filter)
        count_query = count_query.where(agency_filter)

    if date_from:
        query = query.where(RegulatoryDocument.publication_date >= date_from)
        count_query = count_query.where(RegulatoryDocument.publication_date >= date_from)

    if date_to:
        query = query.where(RegulatoryDocument.publication_date <= date_to)
        count_query = count_query.where(RegulatoryDocument.publication_date <= date_to)

    if related_bill:
        # Cast JSONB to text for case-insensitive substring matching
        bill_filter = func.cast(RegulatoryDocument.related_bill_ids, SAString).ilike(
            f"%{related_bill}%"
        )
        query = query.where(bill_filter)
        count_query = count_query.where(bill_filter)

    if q:
        query = query.where(RegulatoryDocument.title.ilike(f"%{q}%"))
        count_query = count_query.where(RegulatoryDocument.title.ilike(f"%{q}%"))

    total = await db.scalar(count_query)

    query = (
        query.order_by(RegulatoryDocument.publication_date.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(query)
    documents = result.scalars().all()

    latest = max((d.updated_at for d in documents), default=None)

    data = [_to_response(d) for d in documents]

    return RegulatoryDocumentListResponse(
        data=data,
        meta=MetaResponse(
            total_count=total or 0,
            page=page,
            per_page=per_page,
            sources=["federal_register"],
            last_updated=latest.isoformat() if latest else None,
        ),
    )


@router.get("/regulatory/{document_id}", response_model=RegulatoryDocumentResponse)
async def get_regulatory_document(
    document_id: str,
    db: AsyncSession = Depends(get_session),
) -> RegulatoryDocumentResponse:
    """Get a single Federal Register document by its document number."""
    result = await db.execute(
        select(RegulatoryDocument).where(RegulatoryDocument.id == document_id)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Regulatory document not found")

    return _to_response(doc)


def _to_response(doc: RegulatoryDocument) -> RegulatoryDocumentResponse:
    """Map a RegulatoryDocument ORM instance to its Pydantic response."""
    return RegulatoryDocumentResponse(
        id=doc.id,
        document_type=doc.document_type,
        title=doc.title,
        abstract=doc.abstract,
        agency_names=doc.agency_names,
        publication_date=doc.publication_date,
        citation=doc.citation,
        federal_register_url=doc.federal_register_url,
        pdf_url=doc.pdf_url,
        topics=doc.topics,
        cfr_references=doc.cfr_references,
        related_bill_ids=doc.related_bill_ids,
        docket_ids=doc.docket_ids,
        regulation_id_numbers=doc.regulation_id_numbers,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
