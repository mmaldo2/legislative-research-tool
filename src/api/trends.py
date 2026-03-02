"""Trend aggregation endpoints — time-series legislative analytics."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_llm_harness, get_session, limiter, require_tier
from src.llm.harness import LLMHarness
from src.schemas.trend import TrendResponse, TrendSummaryResponse, TrendTopicResponse
from src.services.trend_service import (
    action_count_by_period,
    bill_count_by_period,
    topic_distribution_by_period,
)
from src.utils.csv import csv_response, trend_to_csv

router = APIRouter()

BillGroupBy = Literal["jurisdiction", "topic", "status", "classification"]
ActionGroupBy = Literal["jurisdiction", "action_type", "chamber"]
Bucket = Literal["month", "quarter", "year"]
Format = Literal["json", "csv"]

MAX_DATE_RANGE_DAYS = 1095  # ~3 years


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    """Validate date range constraints."""
    if date_from and date_to:
        if date_from > date_to:
            raise HTTPException(400, detail="date_from must be before date_to")
        if (date_to - date_from).days > MAX_DATE_RANGE_DAYS:
            raise HTTPException(
                400,
                detail=f"Date range cannot exceed {MAX_DATE_RANGE_DAYS} days (~3 years)",
            )


@router.get("/trends/bills", response_model=TrendResponse)
@limiter.limit("30/minute")
async def get_bill_trends(
    request: Request,
    group_by: BillGroupBy = Query("jurisdiction", description="Dimension to group by"),
    bucket: Bucket = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    topic: str | None = Query(None, description="Filter by topic (ARRAY containment)"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: Format = Query("json"),
    db: AsyncSession = Depends(get_session),
):
    """Bill counts grouped by time bucket and dimension."""
    _validate_date_range(date_from, date_to)

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
        csv_content = trend_to_csv(result.data, ["period", "dimension", "count"])
        return csv_response(csv_content, "bill_trends.csv")

    return result


@router.get("/trends/actions", response_model=TrendResponse)
@limiter.limit("30/minute")
async def get_action_trends(
    request: Request,
    group_by: ActionGroupBy = Query("jurisdiction", description="Dimension to group by"),
    bucket: Bucket = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    action_type: str | None = Query(None, description="Filter by action classification"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: Format = Query("json"),
    db: AsyncSession = Depends(get_session),
):
    """Action counts grouped by time bucket and dimension."""
    _validate_date_range(date_from, date_to)

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
        csv_content = trend_to_csv(result.data, ["period", "dimension", "count"])
        return csv_response(csv_content, "action_trends.csv")

    return result


@router.get("/trends/topics", response_model=TrendTopicResponse)
@limiter.limit("30/minute")
async def get_topic_trends(
    request: Request,
    bucket: Bucket = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    format: Format = Query("json"),
    db: AsyncSession = Depends(get_session),
):
    """Topic distribution over time with percentage share."""
    _validate_date_range(date_from, date_to)

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
        csv_content = trend_to_csv(
            result.data, ["period", "dimension", "count", "share_pct"]
        )
        return csv_response(csv_content, "topic_trends.csv")

    return result


@router.get("/trends/summary", dependencies=[Depends(require_tier("pro", "enterprise"))])
@limiter.limit("5/minute")
async def get_trend_summary(
    request: Request,
    bucket: Bucket = Query("month", description="Time bucket: month, quarter, year"),
    date_from: date | None = Query(None, description="Start date (inclusive)"),
    date_to: date | None = Query(None, description="End date (inclusive)"),
    jurisdiction: str | None = Query(None, description="Filter by jurisdiction ID"),
    topic: str | None = Query(None, description="Filter by topic"),
    session_id: str | None = Query(None, description="Filter by legislative session"),
    top_n: int = Query(15, ge=1, le=50, description="Max dimension values"),
    db: AsyncSession = Depends(get_session),
    harness: LLMHarness = Depends(get_llm_harness),
) -> TrendSummaryResponse:
    """LLM-generated trend narrative from aggregated data (pro+ tier)."""
    _validate_date_range(date_from, date_to)

    # Run the three aggregation queries while we still hold the session
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

    return await harness.generate_trend_narrative(
        bills_data=bills,
        actions_data=actions,
        topics_data=topics,
        bucket=bucket,
        group_by="jurisdiction",
    )
