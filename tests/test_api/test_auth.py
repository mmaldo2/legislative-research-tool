"""Tests for authentication dependencies and tier enforcement."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.services.auth_service import AuthContext


class TestRequireApiKey:
    """Tests for the require_api_key dependency."""

    @pytest.mark.asyncio
    async def test_dev_mode_no_key_configured(self):
        """When no API key is configured and none provided, returns dev context."""
        from src.api.deps import require_api_key

        with patch("src.api.deps.settings") as mock_settings:
            mock_settings.api_key = ""
            session = AsyncMock()
            result = await require_api_key(api_key=None, db=session)
            assert result.tier == "dev"
            assert result.org_id is None

    @pytest.mark.asyncio
    async def test_legacy_static_key_match(self):
        """Legacy static key check passes in backward-compatible mode."""
        from src.api.deps import require_api_key

        with patch("src.api.deps.settings") as mock_settings:
            mock_settings.api_key = "static-key-123"
            session = AsyncMock()
            result = await require_api_key(api_key="static-key-123", db=session)
            assert result.tier == "dev"

    @pytest.mark.asyncio
    async def test_missing_key_when_required_raises_401(self):
        """When API key is required but not provided, raises 401."""
        from fastapi import HTTPException

        from src.api.deps import require_api_key

        with patch("src.api.deps.settings") as mock_settings:
            mock_settings.api_key = "configured"
            session = AsyncMock()
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key=None, db=session)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_db_key_raises_401(self):
        """Invalid API key (not in DB) raises 401."""
        from fastapi import HTTPException

        from src.api.deps import require_api_key

        with (
            patch("src.api.deps.settings") as mock_settings,
            patch("src.api.deps.verify_api_key", new_callable=AsyncMock) as mock_verify,
        ):
            mock_settings.api_key = ""
            mock_verify.return_value = None
            session = AsyncMock()
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="sk_live_badkey", db=session)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_db_key_returns_context(self):
        """Valid DB-backed API key returns the org context."""
        org_id = uuid.uuid4()
        from src.api.deps import require_api_key

        with (
            patch("src.api.deps.settings") as mock_settings,
            patch("src.api.deps.verify_api_key", new_callable=AsyncMock) as mock_verify,
        ):
            mock_settings.api_key = ""
            mock_verify.return_value = AuthContext(org_id=org_id, tier="pro")
            session = AsyncMock()
            result = await require_api_key(api_key="sk_live_goodkey", db=session)
            assert result.org_id == org_id
            assert result.tier == "pro"


class TestRequireTier:
    """Tests for the require_tier dependency factory."""

    def test_tier_enforcement_via_app(self):
        """Pro+ endpoints reject free tier keys."""
        from src.api.deps import require_api_key, require_tier

        # Create a minimal test app with a tier-gated route
        test_app = FastAPI()

        @test_app.get("/pro-only", dependencies=[Depends(require_tier("pro", "enterprise"))])
        async def pro_only():
            return {"status": "ok"}

        @test_app.get("/any-tier", dependencies=[Depends(require_api_key)])
        async def any_tier():
            return {"status": "ok"}

        client = TestClient(test_app)

        # Free tier should be rejected
        test_app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="free"
        )
        response = client.get("/pro-only")
        assert response.status_code == 403

        # Pro tier should pass
        test_app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="pro"
        )
        response = client.get("/pro-only")
        assert response.status_code == 200

        # Enterprise tier should pass
        test_app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="enterprise"
        )
        response = client.get("/pro-only")
        assert response.status_code == 200

        # Dev mode always passes
        test_app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=None, tier="dev"
        )
        response = client.get("/pro-only")
        assert response.status_code == 200

        test_app.dependency_overrides = {}

    def test_free_tier_can_access_non_gated(self):
        """Free tier can access endpoints without tier gating."""
        from src.api.deps import require_api_key

        test_app = FastAPI()

        @test_app.get("/open", dependencies=[Depends(require_api_key)])
        async def open_route():
            return {"status": "ok"}

        client = TestClient(test_app)
        test_app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="free"
        )
        response = client.get("/open")
        assert response.status_code == 200
        test_app.dependency_overrides = {}


class TestAppTierGating:
    """Test that the actual app routes enforce correct tier requirements."""

    @pytest.fixture
    def client(self):
        from src.api.app import app

        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        from src.api.app import app

        app.dependency_overrides = {}

    def test_bills_accessible_by_free_tier(self, client):
        """Bills endpoint is accessible by all tiers (not 403)."""
        from src.api.app import app
        from src.api.deps import get_session, require_api_key

        mock_session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(side_effect=[count_result, list_result])

        async def _gen():
            yield mock_session

        app.dependency_overrides[get_session] = _gen
        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="free"
        )
        response = client.get("/api/v1/bills")
        # Should NOT be 403 — free tier can access bill listing
        assert response.status_code != 403

    def test_analysis_blocked_for_free_tier(self, client):
        """Analysis endpoints require pro+ tier."""
        from src.api.app import app
        from src.api.deps import require_api_key

        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="free"
        )
        response = client.post(
            "/api/v1/analyze/summarize",
            json={"bill_id": "test"},
        )
        assert response.status_code == 403

    def test_chat_blocked_for_free_tier(self, client):
        """Chat endpoints require pro+ tier."""
        from src.api.app import app
        from src.api.deps import require_api_key

        app.dependency_overrides[require_api_key] = lambda: AuthContext(
            org_id=uuid.uuid4(), tier="free"
        )
        response = client.post(
            "/api/v1/chat",
            json={"message": "test"},
        )
        assert response.status_code == 403


class TestSchemaValidation:
    """Tests for organization and API key schema validation."""

    def test_org_slug_valid_patterns(self):
        from src.schemas.organization import OrgCreate

        # Valid slugs
        for slug in ["my-org", "acme", "test-123", "ab"]:
            org = OrgCreate(name="Test", slug=slug)
            assert org.slug == slug

    def test_org_slug_invalid_patterns(self):
        from pydantic import ValidationError

        from src.schemas.organization import OrgCreate

        # Invalid slugs
        for slug in ["-bad", "bad-", "BAD", "bad slug", "a"]:
            with pytest.raises(ValidationError):
                OrgCreate(name="Test", slug=slug)

    def test_api_key_create_validates_name(self):
        from pydantic import ValidationError

        from src.schemas.api_key import APIKeyCreate

        # Valid
        key = APIKeyCreate(name="Production Key")
        assert key.name == "Production Key"

        # Empty name invalid
        with pytest.raises(ValidationError):
            APIKeyCreate(name="")

    def test_api_key_response_excludes_full_key(self):
        """APIKeyResponse schema does not have a full key field."""
        from src.schemas.api_key import APIKeyResponse

        fields = set(APIKeyResponse.model_fields.keys())
        assert "api_key" not in fields
        assert "key_hash" not in fields
        assert "key_hint" in fields

    def test_api_key_created_response_includes_full_key(self):
        """APIKeyCreatedResponse includes the full key for initial display."""
        from src.schemas.api_key import APIKeyCreatedResponse

        fields = set(APIKeyCreatedResponse.model_fields.keys())
        assert "api_key" in fields
