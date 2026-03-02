"""Tests for webhook endpoint management API."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.deps import get_session, require_api_key
from src.services.auth_service import AuthContext


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def org_id():
    return uuid.uuid4()


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides = {}


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


def _mock_endpoint(org_id, **overrides):
    defaults = {
        "id": uuid.uuid4(),
        "org_id": org_id,
        "url": "https://example.com/webhook",
        "secret": "test-secret-key",
        "is_active": True,
        "failure_count": 0,
        "created_at": datetime(2026, 3, 1),
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def _mock_delivery(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "endpoint_id": uuid.uuid4(),
        "event_type": "bill.created",
        "idempotency_key": "test-key",
        "status": "queued",
        "attempt_count": 0,
        "last_status_code": None,
        "last_error": None,
        "next_retry_at": None,
        "created_at": datetime(2026, 3, 1),
        "delivered_at": None,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


class TestCreateWebhookEndpoint:
    def test_create_returns_201_with_secret(self, client, org_id):
        mock_ep = _mock_endpoint(org_id)
        mock_session = AsyncMock()

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with (
            patch("src.api.webhooks.WebhookEndpoint") as mock_model,
            patch("src.api.webhooks.validate_webhook_url", return_value=None),
            patch("src.api.webhooks.secrets.token_urlsafe", return_value="test-secret-key"),
            patch("src.api.webhooks.encrypt_secret", return_value="encrypted-test-secret"),
        ):
            mock_model.return_value = mock_ep
            response = client.post(
                "/api/v1/webhooks",
                json={"url": "https://example.com/webhook"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com/webhook"
        assert data["is_active"] is True
        assert data["secret"] == "test-secret-key"

    def test_create_requires_org(self, client):
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")
        response = client.post(
            "/api/v1/webhooks",
            json={"url": "https://example.com/webhook"},
        )
        assert response.status_code == 403

    def test_create_invalid_url_returns_422(self, client, org_id):
        mock_session = AsyncMock()

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.post(
            "/api/v1/webhooks",
            json={"url": "not-a-url"},
        )
        assert response.status_code == 422

    def test_create_ssrf_blocked_returns_422(self, client, org_id):
        mock_session = AsyncMock()

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with patch(
            "src.api.webhooks.validate_webhook_url",
            return_value="Webhook URLs must not target private or reserved IP addresses",
        ):
            response = client.post(
                "/api/v1/webhooks",
                json={"url": "https://internal.example.com/webhook"},
            )

        assert response.status_code == 422
        assert "private or reserved" in response.json()["detail"]


class TestListWebhookEndpoints:
    def test_list_returns_org_endpoints(self, client, org_id):
        endpoints = [_mock_endpoint(org_id), _mock_endpoint(org_id)]

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = endpoints
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get("/api/v1/webhooks")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_requires_org(self, client):
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")
        response = client.get("/api/v1/webhooks")
        assert response.status_code == 403


class TestDeleteWebhookEndpoint:
    def test_delete_returns_204(self, client, org_id):
        endpoint_id = uuid.uuid4()
        mock_ep = _mock_endpoint(org_id, id=endpoint_id)

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_ep
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/webhooks/{endpoint_id}")
        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/webhooks/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_delete_wrong_org_returns_404(self, client, org_id):
        """Endpoint belongs to a different org."""
        other_org = uuid.uuid4()

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None  # WHERE org_id won't match
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=other_org, tier="pro"
        )

        response = client.delete(f"/api/v1/webhooks/{uuid.uuid4()}")
        assert response.status_code == 404


class TestListDeliveries:
    def test_list_deliveries_returns_history(self, client, org_id):
        endpoint_id = uuid.uuid4()
        deliveries = [
            _mock_delivery(endpoint_id=endpoint_id, status="delivered"),
            _mock_delivery(endpoint_id=endpoint_id, status="failed"),
        ]

        mock_session = AsyncMock()

        # First execute: verify endpoint belongs to org
        ep_result = MagicMock()
        ep_result.scalar_one_or_none.return_value = _mock_endpoint(org_id, id=endpoint_id)

        # Second execute: get deliveries
        del_result = MagicMock()
        del_result.scalars.return_value.all.return_value = deliveries

        mock_session.execute.side_effect = [ep_result, del_result]

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get(f"/api/v1/webhooks/{endpoint_id}/deliveries")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_deliveries_endpoint_not_found(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get(f"/api/v1/webhooks/{uuid.uuid4()}/deliveries")
        assert response.status_code == 404


class TestTestWebhook:
    def test_send_test_returns_201(self, client, org_id):
        endpoint_id = uuid.uuid4()
        mock_ep = _mock_endpoint(org_id, id=endpoint_id)

        mock_delivery = _mock_delivery(endpoint_id=endpoint_id, status="queued")

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_ep
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with patch("src.api.webhooks.enqueue_delivery", new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = mock_delivery
            response = client.post(f"/api/v1/webhooks/{endpoint_id}/test")

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "queued"
        assert data["message"] == "Test webhook delivery enqueued"

    def test_send_test_endpoint_not_found(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.post(f"/api/v1/webhooks/{uuid.uuid4()}/test")
        assert response.status_code == 404
