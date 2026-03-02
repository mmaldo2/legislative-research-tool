"""Tests for the trend aggregation service."""

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.trend_service import (
    _apply_top_n,
    _cache,
    _cache_key,
    _top_n_dimensions,
    action_count_by_period,
    bill_count_by_period,
    topic_distribution_by_period,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the TTL cache before each test."""
    _cache.clear()
    yield
    _cache.clear()


def _make_row(period, dimension, count):
    """Create a mock row with period, dimension, count attributes."""
    row = MagicMock()
    row.period = period
    row.dimension = dimension
    row.count = count
    return row


class TestCacheKey:
    def test_deterministic(self):
        k1 = _cache_key("bills", "jurisdiction", "month")
        k2 = _cache_key("bills", "jurisdiction", "month")
        assert k1 == k2

    def test_different_params_different_key(self):
        k1 = _cache_key("bills", "jurisdiction", "month")
        k2 = _cache_key("bills", "topic", "month")
        assert k1 != k2


class TestTopNDimensions:
    def test_returns_top_n(self):
        totals = {"a": 100, "b": 50, "c": 200, "d": 10}
        top = _top_n_dimensions(totals, 2)
        assert top == {"c", "a"}

    def test_all_fit(self):
        totals = {"a": 100, "b": 50}
        top = _top_n_dimensions(totals, 5)
        assert top == {"a", "b"}

    def test_empty(self):
        top = _top_n_dimensions({}, 5)
        assert top == set()


class TestApplyTopN:
    def test_all_fit_no_other(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "us-ca", 10),
            _make_row(datetime(2024, 1, 1), "us-tx", 8),
        ]
        data, total = _apply_top_n(rows, top_n=5)
        assert total == 18
        assert len(data) == 2
        dims = {d.dimension for d in data}
        assert "Other" not in dims

    def test_overflow_creates_other(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "us-ca", 100),
            _make_row(datetime(2024, 1, 1), "us-tx", 50),
            _make_row(datetime(2024, 1, 1), "us-ny", 30),
            _make_row(datetime(2024, 1, 1), "us-fl", 20),
        ]
        data, total = _apply_top_n(rows, top_n=2)
        assert total == 200
        dims = {d.dimension for d in data}
        assert "us-ca" in dims
        assert "us-tx" in dims
        assert "Other" in dims
        other = next(d for d in data if d.dimension == "Other")
        assert other.count == 50  # 30 + 20

    def test_empty_rows(self):
        data, total = _apply_top_n([], top_n=5)
        assert data == []
        assert total == 0

    def test_other_per_period(self):
        """Other bucket is computed per period, not globally."""
        rows = [
            _make_row(datetime(2024, 1, 1), "a", 100),
            _make_row(datetime(2024, 1, 1), "b", 10),
            _make_row(datetime(2024, 1, 1), "c", 5),
            _make_row(datetime(2024, 2, 1), "a", 80),
            _make_row(datetime(2024, 2, 1), "d", 3),
        ]
        data, total = _apply_top_n(rows, top_n=1)
        assert total == 198
        # Only "a" should be top; b, c, d all go to Other
        other_points = [d for d in data if d.dimension == "Other"]
        assert len(other_points) == 2  # one per period


class TestBillCountByPeriod:
    @pytest.mark.asyncio
    async def test_returns_trend_response(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "us-ca", 10),
            _make_row(datetime(2024, 2, 1), "us-ca", 15),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        response = await bill_count_by_period(
            session,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
        )

        assert response.meta.bucket == "month"
        assert response.meta.group_by == "jurisdiction"
        assert len(response.data) == 2
        assert response.meta.total_count == 25

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        rows = [_make_row(datetime(2024, 1, 1), "us-ca", 10)]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        # First call populates cache
        r1 = await bill_count_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31)
        )
        # Second call should hit cache (no new execute call)
        session.execute.reset_mock()
        r2 = await bill_count_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31)
        )
        session.execute.assert_not_called()
        assert r1.meta.total_count == r2.meta.total_count

    @pytest.mark.asyncio
    async def test_topic_group_by(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "Education", 20),
            _make_row(datetime(2024, 1, 1), "Healthcare", 15),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        response = await bill_count_by_period(
            session,
            group_by="topic",
            date_from=date(2024, 1, 1),
            date_to=date(2024, 12, 31),
        )
        assert response.meta.group_by == "topic"
        assert response.meta.total_count == 35

    @pytest.mark.asyncio
    async def test_empty_result(self):
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = []
        session.execute.return_value = result

        response = await bill_count_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31)
        )
        assert response.data == []
        assert response.meta.total_count == 0


class TestActionCountByPeriod:
    @pytest.mark.asyncio
    async def test_returns_trend_response(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "us-ca", 50),
            _make_row(datetime(2024, 2, 1), "us-ca", 60),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        response = await action_count_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31)
        )
        assert response.meta.total_count == 110
        assert len(response.data) == 2


class TestTopicDistributionByPeriod:
    @pytest.mark.asyncio
    async def test_includes_share_pct(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "Education", 60),
            _make_row(datetime(2024, 1, 1), "Healthcare", 40),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        response = await topic_distribution_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31)
        )
        assert response.meta.group_by == "topic"
        edu = next(d for d in response.data if d.dimension == "Education")
        assert edu.share_pct == 60.0
        hc = next(d for d in response.data if d.dimension == "Healthcare")
        assert hc.share_pct == 40.0

    @pytest.mark.asyncio
    async def test_other_bucket_with_share_pct(self):
        rows = [
            _make_row(datetime(2024, 1, 1), "Education", 50),
            _make_row(datetime(2024, 1, 1), "Healthcare", 30),
            _make_row(datetime(2024, 1, 1), "Defense", 20),
        ]
        session = AsyncMock()
        result = MagicMock()
        result.all.return_value = rows
        session.execute.return_value = result

        response = await topic_distribution_by_period(
            session, date_from=date(2024, 1, 1), date_to=date(2024, 12, 31), top_n=2
        )
        other = next(d for d in response.data if d.dimension == "Other")
        assert other.count == 20
        assert other.share_pct == 20.0  # 20/100 * 100
