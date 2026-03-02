"""Tests for trend aggregation API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_llm_harness, get_session, require_api_key
from src.schemas.trend import (
    TrendDataPoint,
    TrendMeta,
    TrendResponse,
    TrendSummaryResponse,
    TrendTopicDataPoint,
    TrendTopicResponse,
)
from src.services.auth_service import AuthContext


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides = {}


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


def _sample_trend_response():
    return TrendResponse(
        data=[
            TrendDataPoint(period="2024-01-01", dimension="us-ca", count=10),
            TrendDataPoint(period="2024-02-01", dimension="us-ca", count=15),
        ],
        meta=TrendMeta(
            sources=["govinfo", "openstates"],
            total_count=25,
            bucket="month",
            group_by="jurisdiction",
            date_from="2024-01-01",
            date_to="2024-12-31",
        ),
    )


def _sample_topic_response():
    return TrendTopicResponse(
        data=[
            TrendTopicDataPoint(
                period="2024-01-01", dimension="Education", count=60, share_pct=60.0
            ),
            TrendTopicDataPoint(
                period="2024-01-01", dimension="Healthcare", count=40, share_pct=40.0
            ),
        ],
        meta=TrendMeta(
            sources=["govinfo"],
            total_count=100,
            bucket="month",
            group_by="topic",
            date_from="2024-01-01",
            date_to="2024-12-31",
        ),
    )


class TestGetBillTrends:
    def test_returns_json_by_default(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            response = client.get("/api/v1/trends/bills")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert len(data["data"]) == 2
        assert data["meta"]["bucket"] == "month"

    def test_returns_csv_format(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            response = client.get("/api/v1/trends/bills?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "bill_trends.csv" in response.headers.get("content-disposition", "")
        lines = response.text.strip().splitlines()
        assert lines[0] == "period,dimension,count"
        assert len(lines) == 3  # header + 2 data rows

    def test_passes_query_params_to_service(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            client.get(
                "/api/v1/trends/bills?group_by=topic&bucket=quarter&jurisdiction=us-ca&top_n=10"
            )

        call_kwargs = mock_fn.call_args[1]
        assert call_kwargs["group_by"] == "topic"
        assert call_kwargs["bucket"] == "quarter"
        assert call_kwargs["jurisdiction"] == "us-ca"
        assert call_kwargs["top_n"] == 10

    def test_invalid_bucket_returns_422(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.get("/api/v1/trends/bills?bucket=invalid")
        assert response.status_code == 422

    def test_invalid_group_by_returns_422(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.get("/api/v1/trends/bills?group_by=invalid")
        assert response.status_code == 422


class TestGetActionTrends:
    def test_returns_json(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.action_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            response = client.get("/api/v1/trends/actions")

        assert response.status_code == 200
        assert len(response.json()["data"]) == 2

    def test_csv_format(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.action_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            response = client.get("/api/v1/trends/actions?format=csv")

        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "action_trends.csv" in response.headers.get("content-disposition", "")


class TestGetTopicTrends:
    def test_returns_json_with_share_pct(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch(
            "src.api.trends.topic_distribution_by_period", new_callable=AsyncMock
        ) as mock_fn:
            mock_fn.return_value = _sample_topic_response()
            response = client.get("/api/v1/trends/topics")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2
        assert "share_pct" in data[0]
        assert data[0]["share_pct"] == 60.0

    def test_csv_includes_share_pct_column(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch(
            "src.api.trends.topic_distribution_by_period", new_callable=AsyncMock
        ) as mock_fn:
            mock_fn.return_value = _sample_topic_response()
            response = client.get("/api/v1/trends/topics?format=csv")

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        assert "share_pct" in lines[0]


class TestGetTrendSummary:
    def test_requires_pro_tier(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="free")

        response = client.get("/api/v1/trends/summary")
        assert response.status_code == 403

    def test_dev_mode_passes(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        summary = TrendSummaryResponse(
            narrative="Legislative activity increased.",
            key_findings=["Finding 1"],
            period_covered="2024-01 to 2024-12",
            bills_analyzed=100,
            confidence=0.85,
        )

        mock_harness = MagicMock()
        mock_harness.generate_trend_narrative = AsyncMock(return_value=summary)
        app.dependency_overrides[get_llm_harness] = lambda: mock_harness

        with (
            patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_bills,
            patch("src.api.trends.action_count_by_period", new_callable=AsyncMock) as mock_actions,
            patch(
                "src.api.trends.topic_distribution_by_period", new_callable=AsyncMock
            ) as mock_topics,
        ):
            mock_bills.return_value = _sample_trend_response()
            mock_actions.return_value = _sample_trend_response()
            mock_topics.return_value = _sample_topic_response()

            response = client.get("/api/v1/trends/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["narrative"] == "Legislative activity increased."
        assert len(data["key_findings"]) == 1
        assert data["confidence"] == 0.85

    def test_pro_tier_passes(self, client):
        import uuid

        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="pro"
        )

        summary = TrendSummaryResponse(
            narrative="Summary text.",
            key_findings=[],
            period_covered="2024-01 to 2024-12",
            bills_analyzed=50,
            confidence=0.7,
        )

        mock_harness = MagicMock()
        mock_harness.generate_trend_narrative = AsyncMock(return_value=summary)
        app.dependency_overrides[get_llm_harness] = lambda: mock_harness

        with (
            patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_bills,
            patch("src.api.trends.action_count_by_period", new_callable=AsyncMock) as mock_actions,
            patch(
                "src.api.trends.topic_distribution_by_period", new_callable=AsyncMock
            ) as mock_topics,
        ):
            mock_bills.return_value = _sample_trend_response()
            mock_actions.return_value = _sample_trend_response()
            mock_topics.return_value = _sample_topic_response()

            response = client.get("/api/v1/trends/summary")

        assert response.status_code == 200


class TestDateRangeValidation:
    def test_date_from_after_date_to_returns_400(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.get("/api/v1/trends/bills?date_from=2024-12-01&date_to=2024-01-01")
        assert response.status_code == 400
        assert "date_from must be before date_to" in response.json()["detail"]

    def test_date_range_exceeds_max_returns_400(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.get("/api/v1/trends/bills?date_from=2020-01-01&date_to=2024-12-31")
        assert response.status_code == 400
        assert "cannot exceed" in response.json()["detail"]

    def test_valid_date_range_passes(self, client):
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        with patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = _sample_trend_response()
            response = client.get("/api/v1/trends/bills?date_from=2024-01-01&date_to=2024-12-31")

        assert response.status_code == 200


class TestSchemaValidation:
    def test_trend_data_point(self):
        p = TrendDataPoint(period="2024-01-01", dimension="us-ca", count=42)
        assert p.period == "2024-01-01"
        assert p.count == 42

    def test_trend_topic_data_point_has_share_pct(self):
        p = TrendTopicDataPoint(
            period="2024-01-01", dimension="Education", count=50, share_pct=33.3
        )
        assert p.share_pct == 33.3

    def test_trend_summary_response(self):
        s = TrendSummaryResponse(
            narrative="text",
            key_findings=["a", "b"],
            period_covered="2024-01 to 2024-12",
            bills_analyzed=100,
            confidence=0.9,
        )
        assert len(s.key_findings) == 2
        assert s.confidence == 0.9

    def test_trend_summary_confidence_bounds(self):
        """Confidence must be between 0.0 and 1.0."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TrendSummaryResponse(confidence=1.5)
        with pytest.raises(ValidationError):
            TrendSummaryResponse(confidence=-0.1)

    def test_trend_meta_defaults(self):
        m = TrendMeta()
        assert m.bucket == "month"
        assert m.group_by == "jurisdiction"

    def test_trend_meta_inherits_meta_response_fields(self):
        """TrendMeta inherits ai_enriched, ai_model, etc. from MetaResponse."""
        m = TrendMeta()
        assert hasattr(m, "ai_enriched")
        assert hasattr(m, "ai_model")
        assert m.ai_enriched is False

    def test_trend_summary_has_provenance_fields(self):
        s = TrendSummaryResponse(ai_model="claude-3", ai_prompt_version="v1")
        assert s.ai_model == "claude-3"
        assert s.ai_prompt_version == "v1"


class TestCSVSanitization:
    def test_formula_injection_sanitized(self, client):
        """Ensure values starting with = are sanitized in CSV output."""
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        malicious_response = TrendResponse(
            data=[
                TrendDataPoint(period="2024-01-01", dimension="=CMD()", count=1),
            ],
            meta=TrendMeta(),
        )

        with patch("src.api.trends.bill_count_by_period", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = malicious_response
            response = client.get("/api/v1/trends/bills?format=csv")

        assert response.status_code == 200
        # The = should be sanitized with a leading quote
        assert "'=CMD()" in response.text

    def test_pipe_and_semicolon_sanitized(self, client):
        """Pipe and semicolon prefixes are also dangerous (OWASP)."""
        mock_session = AsyncMock()
        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        for prefix in ["|", ";"]:
            malicious_response = TrendResponse(
                data=[
                    TrendDataPoint(
                        period="2024-01-01", dimension=f"{prefix}cmd", count=1
                    ),
                ],
                meta=TrendMeta(),
            )

            with patch(
                "src.api.trends.bill_count_by_period", new_callable=AsyncMock
            ) as mock_fn:
                mock_fn.return_value = malicious_response
                response = client.get("/api/v1/trends/bills?format=csv")

            assert response.status_code == 200
            assert f"'{prefix}cmd" in response.text


class TestLLMPromptFormatting:
    def test_prompt_template_formats(self):
        from src.llm.prompts.trend_narrative_v1 import USER_PROMPT_TEMPLATE

        formatted = USER_PROMPT_TEMPLATE.format(
            period_covered="2024-01 to 2024-12",
            group_by="jurisdiction",
            bucket="month",
            bills_data="2024-01-01 | us-ca: 10",
            actions_data="2024-01-01 | us-ca: 50",
            topics_data="2024-01-01 | Education: 20 (30%)",
            total_bills=100,
        )
        assert "2024-01 to 2024-12" in formatted
        assert "jurisdiction" in formatted
        assert "100" in formatted

    def test_prompt_has_data_boundaries(self):
        from src.llm.prompts.trend_narrative_v1 import SYSTEM_PROMPT

        assert "<data>" in SYSTEM_PROMPT or "data" in SYSTEM_PROMPT.lower()

    def test_system_prompt_warns_about_data_sections(self):
        from src.llm.prompts.trend_narrative_v1 import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

        assert "raw" in SYSTEM_PROMPT.lower() or "data" in SYSTEM_PROMPT.lower()
        assert "<data>" in USER_PROMPT_TEMPLATE
        assert "</data>" in USER_PROMPT_TEMPLATE
