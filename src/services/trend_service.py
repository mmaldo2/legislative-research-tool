"""Trend aggregation service — time-bucketed queries for legislative analytics."""

import hashlib
import logging
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Protocol, runtime_checkable

from cachetools import TTLCache
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bill import Bill
from src.models.bill_action import BillAction
from src.schemas.trend import (
    TrendDataPoint,
    TrendMeta,
    TrendResponse,
    TrendTopicDataPoint,
    TrendTopicResponse,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class AggregateRow(Protocol):
    """Protocol for rows returned by aggregation queries."""

    period: datetime
    dimension: str
    count: int

# In-process TTL cache: 256 entries, 5 minute TTL
_cache: TTLCache = TTLCache(maxsize=256, ttl=300)

VALID_BUCKETS = {"month", "quarter", "year"}
VALID_BILL_GROUP_BY = {"jurisdiction", "topic", "status", "classification"}
VALID_ACTION_GROUP_BY = {"jurisdiction", "action_type", "chamber"}


def _cache_key(*args: object) -> str:
    """Build a deterministic cache key from query parameters."""
    raw = ":".join(str(a) for a in args)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _default_date_from() -> date:
    return date.today() - timedelta(days=730)  # ~24 months


def _default_date_to() -> date:
    return date.today()


def _validate_bucket(bucket: str) -> str:
    """Validate and return bucket, raising ValueError if invalid."""
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"Invalid bucket: {bucket!r}. Must be one of {sorted(VALID_BUCKETS)}")
    return bucket


def _validate_group_by(group_by: str, valid_set: set[str]) -> str:
    """Validate and return group_by, raising ValueError if invalid."""
    if group_by not in valid_set:
        raise ValueError(f"Invalid group_by: {group_by!r}. Must be one of {sorted(valid_set)}")
    return group_by


async def bill_count_by_period(
    session: AsyncSession,
    *,
    group_by: str = "jurisdiction",
    bucket: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    jurisdiction: str | None = None,
    topic: str | None = None,
    session_id: str | None = None,
    top_n: int = 15,
) -> TrendResponse:
    """Aggregate bill counts by time bucket and dimension."""
    bucket = _validate_bucket(bucket)
    group_by = _validate_group_by(group_by, VALID_BILL_GROUP_BY)
    date_from = date_from or _default_date_from()
    date_to = date_to or _default_date_to()

    key = _cache_key(
        "bills", group_by, bucket, date_from, date_to, jurisdiction, topic, session_id, top_n
    )
    cached = _cache.get(key)
    if cached is not None:
        return cached

    bucket_expr = func.date_trunc(bucket, Bill.created_at).label("period")

    # Build dimension expression based on group_by
    if group_by == "topic":
        dimension_expr = func.unnest(Bill.subject).label("dimension")
    elif group_by == "classification":
        dimension_expr = func.unnest(Bill.classification).label("dimension")
    elif group_by == "status":
        dimension_expr = func.coalesce(Bill.status, "unknown").label("dimension")
    else:  # jurisdiction (default)
        dimension_expr = Bill.jurisdiction_id.label("dimension")

    stmt = (
        select(bucket_expr, dimension_expr, func.count().label("count"))
        .where(Bill.created_at >= date_from, Bill.created_at <= date_to)
        .group_by("period", "dimension")
        .order_by("period")
    )

    # Optional filters
    if jurisdiction:
        stmt = stmt.where(Bill.jurisdiction_id == jurisdiction)
    if topic:
        stmt = stmt.where(Bill.subject.any(topic))
    if session_id:
        stmt = stmt.where(Bill.session_id == session_id)
    if group_by in ("topic", "classification"):
        col = Bill.subject if group_by == "topic" else Bill.classification
        stmt = stmt.where(col.isnot(None))

    result = await session.execute(stmt)
    rows = result.all()

    data, total = _apply_top_n(rows, top_n)

    meta = TrendMeta(
        sources=["govinfo", "openstates", "legiscan"],
        total_count=total,
        bucket=bucket,
        group_by=group_by,
        date_from=str(date_from),
        date_to=str(date_to),
    )
    response = TrendResponse(data=data, meta=meta)
    _cache[key] = response
    return response


async def action_count_by_period(
    session: AsyncSession,
    *,
    group_by: str = "jurisdiction",
    bucket: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    jurisdiction: str | None = None,
    action_type: str | None = None,
    session_id: str | None = None,
    top_n: int = 15,
) -> TrendResponse:
    """Aggregate action counts by time bucket and dimension."""
    bucket = _validate_bucket(bucket)
    group_by = _validate_group_by(group_by, VALID_ACTION_GROUP_BY)
    date_from = date_from or _default_date_from()
    date_to = date_to or _default_date_to()

    key = _cache_key(
        "actions",
        group_by,
        bucket,
        date_from,
        date_to,
        jurisdiction,
        action_type,
        session_id,
        top_n,
    )
    cached = _cache.get(key)
    if cached is not None:
        return cached

    bucket_expr = func.date_trunc(bucket, BillAction.action_date).label("period")

    # Dimension expression — actions need JOIN to bills for jurisdiction
    if group_by == "action_type":
        dimension_expr = func.unnest(BillAction.classification).label("dimension")
    elif group_by == "chamber":
        dimension_expr = func.coalesce(BillAction.chamber, "unknown").label("dimension")
    else:  # jurisdiction (default)
        dimension_expr = Bill.jurisdiction_id.label("dimension")

    stmt = (
        select(bucket_expr, dimension_expr, func.count().label("count"))
        .select_from(BillAction)
        .join(Bill, BillAction.bill_id == Bill.id)
        .where(BillAction.action_date >= date_from, BillAction.action_date <= date_to)
        .group_by("period", "dimension")
        .order_by("period")
    )

    if jurisdiction:
        stmt = stmt.where(Bill.jurisdiction_id == jurisdiction)
    if action_type:
        stmt = stmt.where(BillAction.classification.any(action_type))
    if session_id:
        stmt = stmt.where(Bill.session_id == session_id)
    if group_by == "action_type":
        stmt = stmt.where(BillAction.classification.isnot(None))

    result = await session.execute(stmt)
    rows = result.all()

    data, total = _apply_top_n(rows, top_n)

    meta = TrendMeta(
        sources=["govinfo", "openstates", "legiscan"],
        total_count=total,
        bucket=bucket,
        group_by=group_by,
        date_from=str(date_from),
        date_to=str(date_to),
    )
    response = TrendResponse(data=data, meta=meta)
    _cache[key] = response
    return response


async def topic_distribution_by_period(
    session: AsyncSession,
    *,
    bucket: str = "month",
    date_from: date | None = None,
    date_to: date | None = None,
    jurisdiction: str | None = None,
    session_id: str | None = None,
    top_n: int = 15,
) -> TrendTopicResponse:
    """Aggregate topic distribution with share_pct per period."""
    bucket = _validate_bucket(bucket)
    date_from = date_from or _default_date_from()
    date_to = date_to or _default_date_to()

    key = _cache_key("topics", bucket, date_from, date_to, jurisdiction, session_id, top_n)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    bucket_expr = func.date_trunc(bucket, Bill.created_at).label("period")
    topic_col = func.unnest(Bill.subject).label("dimension")

    stmt = (
        select(bucket_expr, topic_col, func.count().label("count"))
        .where(
            Bill.created_at >= date_from,
            Bill.created_at <= date_to,
            Bill.subject.isnot(None),
        )
        .group_by("period", "dimension")
        .order_by("period")
    )

    if jurisdiction:
        stmt = stmt.where(Bill.jurisdiction_id == jurisdiction)
    if session_id:
        stmt = stmt.where(Bill.session_id == session_id)

    result = await session.execute(stmt)
    rows = result.all()

    # Calculate per-period totals for share_pct
    period_totals: dict[str, int] = {}
    for row in rows:
        period_str = str(row.period.date()) if hasattr(row.period, "date") else str(row.period)
        period_totals[period_str] = period_totals.get(period_str, 0) + row.count

    # Apply top_n across all periods (by total count)
    dimension_totals: dict[str, int] = {}
    total = 0
    for row in rows:
        dimension_totals[row.dimension] = dimension_totals.get(row.dimension, 0) + row.count
        total += row.count

    top_dims = _top_n_dimensions(dimension_totals, top_n)

    # Build data with share_pct, aggregating non-top into "Other"
    period_other: dict[str, int] = {}
    data: list[TrendTopicDataPoint] = []

    for row in rows:
        period_str = str(row.period.date()) if hasattr(row.period, "date") else str(row.period)
        pt = period_totals.get(period_str, 1)

        if row.dimension in top_dims:
            data.append(
                TrendTopicDataPoint(
                    period=period_str,
                    dimension=row.dimension,
                    count=row.count,
                    share_pct=round(row.count / pt * 100, 1),
                )
            )
        else:
            period_other[period_str] = period_other.get(period_str, 0) + row.count

    # Add "Other" buckets
    for period_str, count in sorted(period_other.items()):
        pt = period_totals.get(period_str, 1)
        data.append(
            TrendTopicDataPoint(
                period=period_str,
                dimension="Other",
                count=count,
                share_pct=round(count / pt * 100, 1),
            )
        )

    meta = TrendMeta(
        sources=["govinfo", "openstates", "legiscan"],
        total_count=total,
        bucket=bucket,
        group_by="topic",
        date_from=str(date_from),
        date_to=str(date_to),
    )
    response = TrendTopicResponse(data=data, meta=meta)
    _cache[key] = response
    return response


def _top_n_dimensions(dimension_totals: dict[str, int], top_n: int) -> set[str]:
    """Return the top_n dimensions by total count."""
    sorted_dims = sorted(dimension_totals.items(), key=lambda x: x[1], reverse=True)
    return {dim for dim, _ in sorted_dims[:top_n]}


def _apply_top_n(rows: Sequence[AggregateRow], top_n: int) -> tuple[list[TrendDataPoint], int]:
    """Aggregate rows into TrendDataPoints, collapsing beyond top_n into 'Other'."""
    # Sum total counts per dimension across all periods
    dimension_totals: dict[str, int] = {}
    total = 0
    for row in rows:
        dimension_totals[row.dimension] = dimension_totals.get(row.dimension, 0) + row.count
        total += row.count

    top_dims = _top_n_dimensions(dimension_totals, top_n)

    # Build data points, aggregating non-top into "Other" per period
    period_other: dict[str, int] = {}
    data: list[TrendDataPoint] = []

    for row in rows:
        period_str = str(row.period.date()) if hasattr(row.period, "date") else str(row.period)

        if row.dimension in top_dims:
            data.append(
                TrendDataPoint(
                    period=period_str,
                    dimension=row.dimension,
                    count=row.count,
                )
            )
        else:
            period_other[period_str] = period_other.get(period_str, 0) + row.count

    # Append "Other" data points
    for period_str, count in sorted(period_other.items()):
        data.append(
            TrendDataPoint(
                period=period_str,
                dimension="Other",
                count=count,
            )
        )

    return data, total
