"""Tests for organization API endpoints."""

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


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides = {}


def _override_session(mock_session):
    async def _gen():
        yield mock_session

    return _gen


class TestCreateOrganization:
    def test_create_org_returns_201(self, client):
        """Creating an org returns the org details and an API key."""
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "test-org"
        mock_org.plan = "free"
        mock_org.created_at = datetime(2026, 3, 1)
        mock_org.name = "Test Org"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Slug not taken
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_session] = _override_session(mock_session)

        with patch(
            "src.api.organizations.create_organization", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = (mock_org, "sk_live_testkey1234567890abcdef")
            response = client.post(
                "/api/v1/orgs",
                json={"name": "Test Org", "slug": "test-org"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["organization"]["name"] == "Test Org"
        assert data["organization"]["slug"] == "test-org"
        assert "api_key" in data
        assert "key_hint" in data

    def test_create_org_duplicate_slug_returns_409(self, client):
        """Duplicate slug returns 409 conflict."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # Slug exists
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_session] = _override_session(mock_session)

        response = client.post(
            "/api/v1/orgs",
            json={"name": "Dup Org", "slug": "existing-slug"},
        )
        assert response.status_code == 409
        assert "slug already taken" in response.json()["detail"]

    def test_create_org_invalid_slug_returns_422(self, client):
        """Invalid slug format returns 422."""
        response = client.post(
            "/api/v1/orgs",
            json={"name": "Bad Slug", "slug": "Bad Slug!"},
        )
        assert response.status_code == 422

    def test_create_org_empty_name_returns_422(self, client):
        """Empty name returns 422."""
        response = client.post(
            "/api/v1/orgs",
            json={"name": "", "slug": "valid-slug"},
        )
        assert response.status_code == 422


class TestGetOrganization:
    def test_get_org_returns_details(self, client):
        """Authenticated user can get their org details."""
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "my-org"
        mock_org.plan = "pro"
        mock_org.created_at = datetime(2026, 3, 1)
        mock_org.name = "My Org"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="pro")

        response = client.get(f"/api/v1/orgs/{org_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Org"
        assert data["plan"] == "pro"

    def test_get_org_wrong_org_returns_403(self, client):
        """Cannot access a different organization."""
        org_id = uuid.uuid4()
        other_org_id = uuid.uuid4()

        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=other_org_id, tier="pro"
        )

        response = client.get(f"/api/v1/orgs/{org_id}")
        assert response.status_code == 403

    def test_get_org_not_found_returns_404(self, client):
        """Non-existent org returns 404."""
        org_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=org_id, tier="dev")

        response = client.get(f"/api/v1/orgs/{org_id}")
        assert response.status_code == 404

    def test_get_org_dev_mode_allowed(self, client):
        """Dev mode can access any org."""
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.id = org_id
        mock_org.slug = "dev-org"
        mock_org.plan = "free"
        mock_org.created_at = datetime(2026, 3, 1)
        mock_org.name = "Dev Org"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_org
        mock_session.execute.return_value = mock_result

        app.dependency_overrides[get_session] = _override_session(mock_session)
        app.dependency_overrides[require_api_key] = lambda: AuthContext(org_id=None, tier="dev")

        response = client.get(f"/api/v1/orgs/{org_id}")
        assert response.status_code == 200
