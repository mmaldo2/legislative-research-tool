"""Tests for bill prediction endpoint."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.prediction.schemas import PredictionResponse


@pytest.fixture
def client():
    return TestClient(app)


class TestPredictionSchema:
    def test_prediction_response_validates(self):
        from src.schemas.common import MetaResponse

        resp = PredictionResponse(
            bill_id="abc123",
            committee_passage_probability=0.34,
            model_version="2026-03-18",
            key_factors=[
                {"feature": "action_count", "value": 12.0, "impact": "positive"},
            ],
            base_rate=0.038,
            meta=MetaResponse(sources=["autoresearch-model"], ai_enriched=True),
        )
        assert resp.committee_passage_probability == 0.34
        assert resp.model_version == "2026-03-18"
        assert len(resp.key_factors) == 1
        assert resp.key_factors[0].feature == "action_count"

    def test_probability_bounds(self):
        from src.schemas.common import MetaResponse

        with pytest.raises(Exception):
            PredictionResponse(
                bill_id="abc",
                committee_passage_probability=1.5,  # out of bounds
                model_version="v1",
                key_factors=[],
                base_rate=0.0,
                meta=MetaResponse(),
            )


class TestPredictionEndpoint:
    @patch("src.api.prediction.is_model_loaded")
    def test_503_when_model_not_loaded(self, mock_loaded, client):
        mock_loaded.return_value = False

        from src.api.deps import require_tier

        app.dependency_overrides[require_tier("pro", "enterprise")] = lambda: None
        try:
            resp = client.get("/api/v1/bills/abc123/prediction")
            assert resp.status_code == 503
            assert "not loaded" in resp.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.prediction.predict_bill")
    @patch("src.api.prediction.is_model_loaded")
    def test_404_when_bill_not_found(self, mock_loaded, mock_predict, client):
        mock_loaded.return_value = True
        mock_predict.return_value = None

        from src.api.deps import require_tier

        app.dependency_overrides[require_tier("pro", "enterprise")] = lambda: None
        try:
            resp = client.get("/api/v1/bills/nonexistent/prediction")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.prediction.predict_bill")
    @patch("src.api.prediction.is_model_loaded")
    def test_200_with_prediction(self, mock_loaded, mock_predict, client):
        mock_loaded.return_value = True
        mock_predict.return_value = {
            "bill_id": "abc123",
            "committee_passage_probability": 0.42,
            "model_version": "2026-03-18",
            "key_factors": [
                {"feature": "action_count", "value": 15.0, "impact": "positive"},
                {"feature": "cosponsor_count", "value": 8.0, "impact": "positive"},
            ],
            "base_rate": 0.038,
        }

        from src.api.deps import require_tier

        app.dependency_overrides[require_tier("pro", "enterprise")] = lambda: None
        try:
            resp = client.get("/api/v1/bills/abc123/prediction")
            assert resp.status_code == 200
            data = resp.json()
            assert data["bill_id"] == "abc123"
            assert data["committee_passage_probability"] == 0.42
            assert data["model_version"] == "2026-03-18"
            assert len(data["key_factors"]) == 2
            assert data["base_rate"] == 0.038
            assert data["meta"]["ai_enriched"] is True
        finally:
            app.dependency_overrides.clear()
