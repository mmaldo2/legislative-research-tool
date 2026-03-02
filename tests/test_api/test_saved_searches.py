"""Tests for saved search and alert subscription API endpoints."""

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


def _mock_search(org_id, **overrides):
    search_name = overrides.pop("name", "Test Search")
    defaults = {
        "id": uuid.uuid4(),
        "org_id": org_id,
        "criteria": {"jurisdiction_id": "us"},
        "alerts_enabled": False,
        "created_at": datetime(2026, 3, 1),
        "updated_at": datetime(2026, 3, 1),
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    mock.name = search_name
    return mock


class TestCreateSavedSearch:
    def test_create_returns_201(self, client, org_id):
        mock_session = AsyncMock()
        mock_search = _mock_search(org_id)

        # After commit + refresh, return the mock
        mock_session.refresh = AsyncMock(return_value=None)

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with patch("src.api.saved_searches.SavedSearch") as mock_model:
            mock_model.return_value = mock_search
            response = client.post(
                "/api/v1/saved-searches",
                json={"name": "My Search", "criteria": {"query": "privacy"}},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Search"
        assert data["criteria"] == {"jurisdiction_id": "us"}

    def test_create_requires_org(self, client):
        """Dev mode (no org) returns 403."""
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.post(
            "/api/v1/saved-searches",
            json={"name": "S", "criteria": {}},
        )
        assert response.status_code == 403


class TestListSavedSearches:
    def test_list_returns_org_searches(self, client, org_id):
        searches = [_mock_search(org_id, name="S1"), _mock_search(org_id, name="S2")]

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = searches
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get("/api/v1/saved-searches")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_requires_org(self, client):
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")
        response = client.get("/api/v1/saved-searches")
        assert response.status_code == 403


class TestUpdateSavedSearch:
    def test_update_returns_200(self, client, org_id):
        search_id = uuid.uuid4()
        mock = _mock_search(org_id, id=search_id)

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.put(
            f"/api/v1/saved-searches/{search_id}",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200

    def test_update_nonexistent_returns_404(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.put(
            f"/api/v1/saved-searches/{uuid.uuid4()}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404


class TestDeleteSavedSearch:
    def test_delete_returns_204(self, client, org_id):
        search_id = uuid.uuid4()
        mock = _mock_search(org_id, id=search_id)

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/saved-searches/{search_id}")
        assert response.status_code == 204

    def test_delete_nonexistent_returns_404(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/saved-searches/{uuid.uuid4()}")
        assert response.status_code == 404


class TestCreateAlertSubscription:
    def test_create_alert_returns_201(self, client, org_id):
        search_id = uuid.uuid4()
        endpoint_id = uuid.uuid4()
        mock_search_obj = _mock_search(org_id, id=search_id)

        mock_endpoint = MagicMock()
        mock_endpoint.id = endpoint_id
        mock_endpoint.org_id = org_id

        mock_sub = MagicMock()
        mock_sub.id = uuid.uuid4()
        mock_sub.saved_search_id = search_id
        mock_sub.webhook_endpoint_id = endpoint_id
        mock_sub.event_types = ["bill.created"]
        mock_sub.is_active = True
        mock_sub.created_at = datetime(2026, 3, 1)

        mock_session = AsyncMock()
        # First execute: find saved search, second: find endpoint
        search_result = MagicMock()
        search_result.scalar_one_or_none.return_value = mock_search_obj

        ep_result = MagicMock()
        ep_result.scalar_one_or_none.return_value = mock_endpoint

        mock_session.execute.side_effect = [search_result, ep_result]

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with patch("src.api.saved_searches.AlertSubscription") as mock_sub_cls:
            mock_sub_cls.return_value = mock_sub
            response = client.post(
                f"/api/v1/saved-searches/{search_id}/alerts",
                json={
                    "webhook_endpoint_id": str(endpoint_id),
                    "event_types": ["bill.created"],
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["event_types"] == ["bill.created"]

    def test_create_alert_search_not_found_returns_404(self, client, org_id):
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.post(
            f"/api/v1/saved-searches/{uuid.uuid4()}/alerts",
            json={
                "webhook_endpoint_id": str(uuid.uuid4()),
                "event_types": ["bill.created"],
            },
        )
        assert response.status_code == 404

    def test_create_alert_endpoint_not_found_returns_404(self, client, org_id):
        search_id = uuid.uuid4()
        mock_search_obj = _mock_search(org_id, id=search_id)

        mock_session = AsyncMock()
        search_result = MagicMock()
        search_result.scalar_one_or_none.return_value = mock_search_obj

        ep_result = MagicMock()
        ep_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [search_result, ep_result]

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.post(
            f"/api/v1/saved-searches/{search_id}/alerts",
            json={
                "webhook_endpoint_id": str(uuid.uuid4()),
                "event_types": ["bill.created"],
            },
        )
        assert response.status_code == 404
