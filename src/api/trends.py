"""Trend aggregation endpoints — time-series legislative analytics."""

import csv
import io
import re
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter, require_tier
from src.schemas.trend import TrendSummaryResponse
from src.services.trend_service import (
    VALID_ACTION_GROUP_BY,
    VALID_BILL_GROUP_BY,
    VALID_BUCKETS,
    action_count_by_period,
    bill_count_by_period,
    topic_distribution_by_period,
)

router = APIRouter()

_CSV_FORMULA_RE = re.compile(r"^[=+\-@\t\r]")


def _sanitize_csv(value: str) -> str:
    """Prepend a single quote to values that could trigger spreadsheet formula injection."""
    if _CSV_FORMULA_RE.match(value):
        return "'" + value
    return value


def _trend_to_csv(data: list, columns: list[str]) -> str:
    """Convert trend data points to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for point in data:
        row = [_sanitize_csv(str(getattr(point, col, ""))) for col in columns]
        writer.writerow(row)
    output.seek(0)
    return output.getvalue()


def _csv_response(csv_content: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/trends/bills", response_model=None)
@limiter.limit("30/minute")
async def get_bill_trends(
    request: Request,
    group_by: str = Query("jurisdiction", description="Dimension to group by"),
    bucket: str = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    topic: str | None = Query(None, description="Filter by topic (ARRAY containment)"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_session),
):
    """Bill counts grouped by time bucket and dimension."""
    if bucket not in VALID_BUCKETS:
        bucket = "month"
    if group_by not in VALID_BILL_GROUP_BY:
        group_by = "jurisdiction"

    result = await bill_count_by_period(
        db,
        group_by=group_by,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        topic=topic,
        session_id=session_id,
        top_n=top_n,
    )

    if format == "csv":
        csv_content = _trend_to_csv(result.data, ["period", "dimension", "count"])
        return _csv_response(csv_content, "bill_trends.csv")

    return result


@router.get("/trends/actions", response_model=None)
@limiter.limit("30/minute")
async def get_action_trends(
    request: Request,
    group_by: str = Query("jurisdiction", description="Dimension to group by"),
    bucket: str = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    action_type: str | None = Query(None, description="Filter by action classification"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_session),
):
    """Action counts grouped by time bucket and dimension."""
    if bucket not in VALID_BUCKETS:
        bucket = "month"
    if group_by not in VALID_ACTION_GROUP_BY:
        group_by = "jurisdiction"

    result = await action_count_by_period(
        db,
        group_by=group_by,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        action_type=action_type,
        session_id=session_id,
        top_n=top_n,
    )

    if format == "csv":
        csv_content = _trend_to_csv(result.data, ["period", "dimension", "count"])
        return _csv_response(csv_content, "action_trends.csv")

    return result


@router.get("/trends/topics", response_model=None)
@limiter.limit("30/minute")
async def get_topic_trends(
    request: Request,
    bucket: str = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_session),
):
    """Topic distribution over time with percentage share."""
    if bucket not in VALID_BUCKETS:
        bucket = "month"

    result = await topic_distribution_by_period(
        db,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        session_id=session_id,
        top_n=top_n,
    )

    if format == "csv":
        csv_content = _trend_to_csv(result.data, ["period", "dimension", "count", "share_pct"])
        return _csv_response(csv_content, "topic_trends.csv")

    return result


@router.get("/trends/summary", dependencies=[Depends(require_tier("pro", "enterprise"))])
@limiter.limit("5/minute")
async def get_trend_summary(
    request: Request,
    bucket: str = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    topic: str | None = Query(None, description="Filter by topic"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    db: AsyncSession = Depends(get_session),
) -> TrendSummaryResponse:
    """LLM-generated trend narrative from aggregated data (pro+ tier)."""
    from src.api.deps import get_anthropic_client
    from src.llm.harness import LLMHarness

    if bucket not in VALID_BUCKETS:
        bucket = "month"

    # Run the three aggregation queries to feed the LLM
    bills = await bill_count_by_period(
        db,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        topic=topic,
        session_id=session_id,
        top_n=top_n,
    )
    actions = await action_count_by_period(
        db,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        session_id=session_id,
        top_n=top_n,
    )
    topics = await topic_distribution_by_period(
        db,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        jurisdiction=jurisdiction,
        session_id=session_id,
        top_n=top_n,
    )

    harness = LLMHarness(db_session=db, client=get_anthropic_client())
    return await harness.generate_trend_narrative(
        bills_data=bills,
        actions_data=actions,
        topics_data=topics,
        bucket=bucket,
        group_by="jurisdiction",
    )
