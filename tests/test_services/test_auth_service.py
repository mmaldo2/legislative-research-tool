"""Tests for the authentication service."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.auth_service import (
    AuthContext,
    generate_api_key,
    hash_api_key,
    slugify,
    verify_api_key,
)


class TestGenerateApiKey:
    def test_returns_three_tuple(self):
        full_key, hint, key_hash = generate_api_key()
        assert isinstance(full_key, str)
        assert isinstance(hint, str)
        assert isinstance(key_hash, str)

    def test_default_prefix(self):
        full_key, _, _ = generate_api_key()
        assert full_key.startswith("sk_live_")

    def test_custom_prefix(self):
        full_key, _, _ = generate_api_key(prefix="sk_test_")
        assert full_key.startswith("sk_test_")

    def test_hint_is_last_4_chars(self):
        full_key, hint, _ = generate_api_key()
        assert hint == full_key[-4:]

    def test_hash_is_sha256(self):
        full_key, _, key_hash = generate_api_key()
        expected = hashlib.sha256(full_key.encode()).hexdigest()
        assert key_hash == expected

    def test_key_length_sufficient(self):
        full_key, _, _ = generate_api_key()
        # prefix (8) + 43 (urlsafe_b64 of 32 bytes) = ~51 chars
        assert len(full_key) > 40

    def test_unique_keys(self):
        keys = {generate_api_key()[0] for _ in range(10)}
        assert len(keys) == 10  # All unique


class TestHashApiKey:
    def test_consistent_hashing(self):
        key = "sk_live_test123"
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self):
        assert hash_api_key("key-a") != hash_api_key("key-b")

    def test_matches_generate(self):
        full_key, _, expected_hash = generate_api_key()
        assert hash_api_key(full_key) == expected_hash


class TestSlugify:
    def test_lowercase(self):
        assert slugify("My Org") == "my-org"

    def test_special_chars(self):
        assert slugify("Org & Co!") == "org-co"

    def test_strips_leading_trailing_hyphens(self):
        assert slugify("--test--") == "test"

    def test_empty_string(self):
        assert slugify("") == "org"

    def test_already_slug(self):
        assert slugify("my-org") == "my-org"


class TestAuthContext:
    def test_dev_mode(self):
        ctx = AuthContext(org_id=None, tier="dev")
        assert ctx.org_id is None
        assert ctx.tier == "dev"

    def test_org_context(self):
        org_id = uuid.uuid4()
        ctx = AuthContext(org_id=org_id, tier="pro")
        assert ctx.org_id == org_id
        assert ctx.tier == "pro"


class TestVerifyApiKey:
    @pytest.mark.asyncio
    async def test_valid_key_returns_context(self):
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.plan = "pro"

        mock_key = MagicMock()
        mock_key.org_id = org_id
        mock_key.organization = mock_org
        mock_key.is_active = True
        mock_key.expires_at = None
        mock_key.last_used_at = None
        mock_key.request_count = 0

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_key
        session.execute.return_value = result

        auth = await verify_api_key(session, "sk_live_testkey123")
        assert auth is not None
        assert auth.org_id == org_id
        assert auth.tier == "pro"

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self):
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result

        auth = await verify_api_key(session, "sk_live_invalid")
        assert auth is None

    @pytest.mark.asyncio
    async def test_expired_key_returns_none(self):
        mock_key = MagicMock()
        mock_key.is_active = True
        mock_key.expires_at = datetime.now(UTC) - timedelta(hours=1)

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_key
        session.execute.return_value = result

        auth = await verify_api_key(session, "sk_live_expired")
        assert auth is None

    @pytest.mark.asyncio
    async def test_updates_usage_stats(self):
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.plan = "free"

        mock_key = MagicMock()
        mock_key.org_id = org_id
        mock_key.organization = mock_org
        mock_key.is_active = True
        mock_key.expires_at = None
        mock_key.last_used_at = None
        mock_key.request_count = 5

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_key
        session.execute.return_value = result

        await verify_api_key(session, "sk_live_testkey")

        assert mock_key.request_count == 6
        assert mock_key.last_used_at is not None
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_expired_key_succeeds(self):
        org_id = uuid.uuid4()
        mock_org = MagicMock()
        mock_org.plan = "enterprise"

        mock_key = MagicMock()
        mock_key.org_id = org_id
        mock_key.organization = mock_org
        mock_key.is_active = True
        mock_key.expires_at = datetime.now(UTC) + timedelta(days=30)
        mock_key.last_used_at = None
        mock_key.request_count = 0

        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = mock_key
        session.execute.return_value = result

        auth = await verify_api_key(session, "sk_live_future")
        assert auth is not None
        assert auth.tier == "enterprise"
