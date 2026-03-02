"""Tests for API key management endpoints."""

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
    """Ensure dependency overrides are cleaned up after each test."""
    yield
    app.dependency_overrides = {}


def _mock_api_key(org_id, **overrides):
    """Create a mock APIKey object."""
    key_name = overrides.pop("name", "Test Key")
    defaults = {
        "id": uuid.uuid4(),
        "org_id": org_id,
        "prefix": "sk_live_",
        "key_hint": "abcd",
        "is_active": True,
        "last_used_at": None,
        "request_count": 0,
        "created_at": datetime(2026, 3, 1),
    }
    defaults.update(overrides)
    mock = MagicMock(**defaults)
    mock.name = key_name
    return mock


def _override_session(mock_session):
    """Create an async generator override for get_session."""

    async def _gen():
        yield mock_session

    return _gen


class TestProvisionApiKey:
    def test_provision_key_returns_201(self, client, org_id):
        """Provisioning a key returns the full key once."""
        key_record = _mock_api_key(org_id)
        full_key = "sk_live_testkey1234567890"

        mock_session = AsyncMock()
        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = MagicMock()
        mock_session.execute.return_value = org_result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        with patch("src.api.api_keys.provision_api_key", new_callable=AsyncMock) as mock_provision:
            mock_provision.return_value = (key_record, full_key)
            response = client.post(
                f"/api/v1/orgs/{org_id}/api-keys",
                json={"name": "CI Key"},
            )

        assert response.status_code == 201
        data = response.json()
        assert "api_key" in data
        assert data["name"] == "Test Key"

    def test_provision_key_wrong_org_returns_403(self, client, org_id):
        """Cannot provision keys for another org."""
        other_org = uuid.uuid4()
        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=other_org, tier="pro"
        )

        response = client.post(
            f"/api/v1/orgs/{org_id}/api-keys",
            json={"name": "Sneaky Key"},
        )
        assert response.status_code == 403

    def test_provision_key_nonexistent_org_returns_404(self, client, org_id):
        """Provisioning key for non-existent org returns 404."""
        mock_session = AsyncMock()
        org_result = MagicMock()
        org_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = org_result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="dev")

        response = client.post(
            f"/api/v1/orgs/{org_id}/api-keys",
            json={"name": "Ghost Key"},
        )
        assert response.status_code == 404


class TestListApiKeys:
    def test_list_keys_returns_hints_only(self, client, org_id):
        """Listing keys returns hints, never full keys."""
        keys = [_mock_api_key(org_id, name="Key 1"), _mock_api_key(org_id, name="Key 2")]

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = keys
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get(f"/api/v1/orgs/{org_id}/api-keys")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        for key in data:
            assert "key_hint" in key
            assert "api_key" not in key

    def test_list_keys_wrong_org_returns_403(self, client, org_id):
        """Cannot list keys for another org."""
        other_org = uuid.uuid4()
        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=other_org, tier="pro"
        )

        response = client.get(f"/api/v1/orgs/{org_id}/api-keys")
        assert response.status_code == 403


class TestRevokeApiKey:
    def test_revoke_key_returns_204(self, client, org_id):
        """Revoking a key soft-deletes it."""
        key_id = uuid.uuid4()
        mock_key = _mock_api_key(org_id, id=key_id)

        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_key
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/orgs/{org_id}/api-keys/{key_id}")

        assert response.status_code == 204
        assert mock_key.is_active is False

    def test_revoke_nonexistent_key_returns_404(self, client, org_id):
        """Revoking a non-existent key returns 404."""
        key_id = uuid.uuid4()
        mock_session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.delete(f"/api/v1/orgs/{org_id}/api-keys/{key_id}")
        assert response.status_code == 404

    def test_revoke_key_wrong_org_returns_403(self, client, org_id):
        """Cannot revoke keys for another org."""
        other_org = uuid.uuid4()
        key_id = uuid.uuid4()

        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=other_org, tier="pro"
        )

        response = client.delete(f"/api/v1/orgs/{org_id}/api-keys/{key_id}")
        assert response.status_code == 403
