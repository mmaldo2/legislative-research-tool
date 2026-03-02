"""Export endpoints — CSV bulk export and single-bill markdown brief."""

import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.deps import escape_like, get_session, limiter
from src.models.bill import Bill
from src.models.bill_text import texts_without_markup
from src.models.sponsorship import Sponsorship
from src.utils.csv import sanitize_csv

router = APIRouter()


@router.get("/export/bills/csv")
@limiter.limit("10/minute")
async def export_bills_csv(
    request: Request,
    bill_ids: str | None = Query(None, description="Comma-separated bill IDs"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    status: str | None = Query(None, description="Filter by bill status"),
    q: str | None = Query(None, description="Search title (case-insensitive contains)"),
    include_summary: bool = Query(False, description="Include AI summary column"),
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export bills as CSV.

    Supports filtering by specific bill IDs, jurisdiction, status, or a title
    search query.  Results are capped at 5 000 rows to protect the server.
    When ``include_summary`` is true, the latest AI plain-english summary is
    appended as an extra column.
    """
    stmt = select(Bill)

    if bill_ids:
        ids = [b.strip() for b in bill_ids.split(",") if b.strip()]
        stmt = stmt.where(Bill.id.in_(ids))
    if jurisdiction:
        stmt = stmt.where(Bill.jurisdiction_id == jurisdiction)
    if status:
        stmt = stmt.where(Bill.status == status)
    if q:
        stmt = stmt.where(Bill.title.ilike(f"%{escape_like(q)}%", escape="\\"))

    if include_summary:
        stmt = stmt.options(selectinload(Bill.analyses))

    stmt = stmt.order_by(Bill.updated_at.desc()).limit(5000)

    result = await db.execute(stmt)
    bills = result.scalars().all()

    # Build CSV in-memory (return headers-only CSV for empty results)
    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "id",
        "identifier",
        "title",
        "jurisdiction_id",
        "session_id",
        "status",
        "status_date",
        "classification",
        "subject",
    ]
    if include_summary:
        headers.append("ai_summary")
    writer.writerow(headers)

    for bill in bills:
        row = [
            bill.id,
            bill.identifier,
            sanitize_csv(bill.title),
            bill.jurisdiction_id,
            bill.session_id,
            bill.status or "",
            str(bill.status_date or ""),
            sanitize_csv("; ".join(bill.classification or [])),
            sanitize_csv("; ".join(bill.subject or [])),
        ]
        if include_summary:
            summary = ""
            for a in bill.analyses:
                if a.analysis_type == "summary" and a.result:
                    summary = a.result.get("plain_english_summary", "")
                    break
            row.append(sanitize_csv(summary))
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bills_export.csv"'},
    )


@router.get("/export/bills/{bill_id}/brief")
@limiter.limit("10/minute")
async def export_bill_brief(
    request: Request,
    bill_id: str,
    db: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Export a single bill as a markdown brief.

    Produces a self-contained Markdown document suitable for sharing or
    conversion to PDF.  Includes metadata, AI summary (if available),
    sponsors, and full legislative action history.
    """
    stmt = (
        select(Bill)
        .where(Bill.id == bill_id)
        .options(
            texts_without_markup(Bill.texts),
            selectinload(Bill.actions),
            selectinload(Bill.sponsorships).selectinload(Sponsorship.person),
            selectinload(Bill.analyses),
        )
    )
    result = await db.execute(stmt)
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    lines: list[str] = []
    lines.append(f"# {bill.identifier}: {bill.title}")
    lines.append("")
    lines.append(f"**Jurisdiction:** {bill.jurisdiction_id}")
    lines.append(f"**Session:** {bill.session_id}")
    lines.append(f"**Status:** {bill.status or 'Unknown'}")
    if bill.status_date:
        lines.append(f"**Status Date:** {bill.status_date}")
    if bill.classification:
        lines.append(f"**Classification:** {', '.join(bill.classification)}")
    if bill.subject:
        lines.append(f"**Subjects:** {', '.join(bill.subject)}")
    lines.append("")

    # AI Summary section
    for a in bill.analyses or []:
        if a.analysis_type == "summary" and a.result:
            lines.append("## AI Summary")
            lines.append("")
            plain = a.result.get("plain_english_summary", "")
            if plain:
                lines.append(plain)
                lines.append("")
            provisions = a.result.get("key_provisions", [])
            if provisions:
                lines.append("### Key Provisions")
                lines.append("")
                for p in provisions:
                    lines.append(f"- {p}")
                lines.append("")
            break

    # Sponsors section
    if bill.sponsorships:
        lines.append("## Sponsors")
        lines.append("")
        for s in bill.sponsorships:
            name = s.person.name if s.person else s.person_id
            party = f" ({s.person.party})" if s.person and s.person.party else ""
            lines.append(f"- {name}{party} — {s.classification}")
        lines.append("")

    # Legislative history section
    if bill.actions:
        lines.append("## Legislative History")
        lines.append("")
        sorted_actions = sorted(bill.actions, key=lambda a: a.action_date)
        for action in sorted_actions:
            lines.append(f"- **{action.action_date}**: {action.description}")
        lines.append("")

    # Bill text versions section
    if bill.texts:
        lines.append("## Text Versions")
        lines.append("")
        for t in bill.texts:
            date_str = f" ({t.version_date})" if t.version_date else ""
            word_str = f" — {t.word_count:,} words" if t.word_count else ""
            lines.append(f"- {t.version_name}{date_str}{word_str}")
        lines.append("")

    content = "\n".join(lines)
    safe_filename = re.sub(r"[^a-zA-Z0-9_-]", "_", bill.identifier)

    return StreamingResponse(
        iter([content]),
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}_brief.md"',
        },
    )
