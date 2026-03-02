"""Tests for the webhook dispatcher service."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.webhook_dispatcher import (
    CIRCUIT_BREAKER_THRESHOLD,
    MAX_ATTEMPTS,
    RETRY_DELAYS,
    deliver_webhook,
    enqueue_delivery,
    sign_payload,
    validate_webhook_url,
    verify_signature,
)


class TestSignPayload:
    def test_returns_signature_and_timestamp_headers(self):
        headers = sign_payload({"key": "value"}, "secret123")
        assert "X-Webhook-Signature" in headers
        assert "X-Webhook-Timestamp" in headers

    def test_signature_format(self):
        headers = sign_payload({"key": "value"}, "secret123")
        sig = headers["X-Webhook-Signature"]
        assert sig.startswith("t=")
        assert ",v1=" in sig

    def test_deterministic_for_same_timestamp(self):
        """Same payload+secret+timestamp produces same signature."""
        with patch("src.services.webhook_dispatcher.time") as mock_time:
            mock_time.time.return_value = 1000000
            h1 = sign_payload({"a": 1}, "secret")
            h2 = sign_payload({"a": 1}, "secret")
        assert h1 == h2

    def test_different_secrets_different_signatures(self):
        with patch("src.services.webhook_dispatcher.time") as mock_time:
            mock_time.time.return_value = 1000000
            h1 = sign_payload({"a": 1}, "secret-a")
            h2 = sign_payload({"a": 1}, "secret-b")
        assert h1["X-Webhook-Signature"] != h2["X-Webhook-Signature"]


class TestVerifySignature:
    def test_valid_signature_passes(self):
        payload = {"event": "test"}
        secret = "my-secret-key"
        headers = sign_payload(payload, secret)
        assert verify_signature(payload, secret, headers["X-Webhook-Signature"]) is True

    def test_wrong_secret_fails(self):
        payload = {"event": "test"}
        headers = sign_payload(payload, "correct-secret")
        assert verify_signature(payload, "wrong-secret", headers["X-Webhook-Signature"]) is False

    def test_tampered_payload_fails(self):
        payload = {"event": "test"}
        headers = sign_payload(payload, "secret")
        tampered = {"event": "hacked"}
        assert verify_signature(tampered, "secret", headers["X-Webhook-Signature"]) is False

    def test_empty_payload(self):
        payload = {}
        secret = "s"
        headers = sign_payload(payload, secret)
        assert verify_signature(payload, secret, headers["X-Webhook-Signature"]) is True


class TestEnqueueDelivery:
    @pytest.mark.asyncio
    async def test_creates_queued_delivery(self):
        session = AsyncMock()
        endpoint = MagicMock()
        endpoint.id = uuid.uuid4()

        delivery = await enqueue_delivery(session, endpoint, "bill.created", {"bill_id": "b1"})

        assert delivery.status == "queued"
        assert delivery.event_type == "bill.created"
        assert delivery.endpoint_id == endpoint.id
        assert delivery.payload == {"bill_id": "b1"}
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_idempotency_key_format(self):
        session = AsyncMock()
        endpoint = MagicMock()
        endpoint.id = uuid.uuid4()

        delivery = await enqueue_delivery(session, endpoint, "bill.updated", {})
        key = delivery.idempotency_key
        assert key.startswith(f"{endpoint.id}:bill.updated:")
        assert len(key.split(":")) == 3

    @pytest.mark.asyncio
    async def test_next_retry_at_is_now(self):
        session = AsyncMock()
        endpoint = MagicMock()
        endpoint.id = uuid.uuid4()

        before = datetime.now(UTC)
        delivery = await enqueue_delivery(session, endpoint, "test", {})
        after = datetime.now(UTC)

        assert delivery.next_retry_at is not None
        assert before <= delivery.next_retry_at <= after


class TestValidateWebhookUrl:
    def test_rejects_http(self):
        assert validate_webhook_url("http://example.com/hook") is not None

    def test_accepts_https(self):
        with patch("src.services.webhook_dispatcher.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),
            ]
            assert validate_webhook_url("https://example.com/hook") is None

    def test_rejects_private_ip(self):
        with patch("src.services.webhook_dispatcher.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("10.0.0.1", 443)),
            ]
            result = validate_webhook_url("https://internal.example.com/hook")
            assert result is not None
            assert "private" in result

    def test_rejects_localhost(self):
        with patch("src.services.webhook_dispatcher.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 443)),
            ]
            result = validate_webhook_url("https://localhost/hook")
            assert result is not None

    def test_rejects_link_local(self):
        with patch("src.services.webhook_dispatcher.socket.getaddrinfo") as mock_dns:
            mock_dns.return_value = [
                (2, 1, 6, "", ("169.254.169.254", 443)),
            ]
            result = validate_webhook_url("https://metadata.internal/hook")
            assert result is not None

    def test_rejects_unresolvable_host(self):
        import socket

        with patch("src.services.webhook_dispatcher.socket.getaddrinfo") as mock_dns:
            mock_dns.side_effect = socket.gaierror("Name or service not known")
            result = validate_webhook_url("https://nonexistent.invalid/hook")
            assert result is not None
            assert "resolve" in result.lower()


class TestDeliverWebhook:
    @pytest.mark.asyncio
    async def test_success_marks_delivered(self):
        delivery = MagicMock()
        delivery.id = uuid.uuid4()
        delivery.payload = {"test": True}
        delivery.event_type = "bill.created"
        delivery.attempt_count = 0

        endpoint = MagicMock()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = "secret"

        mock_response = MagicMock()
        mock_response.status_code = 200

        with (
            patch("src.services.webhook_dispatcher.validate_webhook_url", return_value=None),
            patch("src.services.webhook_dispatcher.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook(delivery, endpoint)

        assert result is True
        assert delivery.status == "delivered"
        assert delivery.delivered_at is not None
        assert delivery.next_retry_at is None

    @pytest.mark.asyncio
    async def test_failure_schedules_retry(self):
        delivery = MagicMock()
        delivery.id = uuid.uuid4()
        delivery.payload = {"test": True}
        delivery.event_type = "bill.created"
        delivery.attempt_count = 0

        endpoint = MagicMock()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = "secret"

        mock_response = MagicMock()
        mock_response.status_code = 500

        with (
            patch("src.services.webhook_dispatcher.validate_webhook_url", return_value=None),
            patch("src.services.webhook_dispatcher.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook(delivery, endpoint)

        assert result is False
        assert delivery.status == "failed"
        assert delivery.attempt_count == 1
        assert delivery.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_max_attempts_dead_letters(self):
        delivery = MagicMock()
        delivery.id = uuid.uuid4()
        delivery.payload = {}
        delivery.event_type = "bill.created"
        delivery.attempt_count = MAX_ATTEMPTS - 1  # Will reach max after increment

        endpoint = MagicMock()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = "secret"

        mock_response = MagicMock()
        mock_response.status_code = 503

        with (
            patch("src.services.webhook_dispatcher.validate_webhook_url", return_value=None),
            patch("src.services.webhook_dispatcher.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook(delivery, endpoint)

        assert result is False
        assert delivery.status == "dead_letter"
        assert delivery.next_retry_at is None

    @pytest.mark.asyncio
    async def test_timeout_records_error(self):
        import httpx

        delivery = MagicMock()
        delivery.id = uuid.uuid4()
        delivery.payload = {}
        delivery.event_type = "test"
        delivery.attempt_count = 0

        endpoint = MagicMock()
        endpoint.url = "https://example.com/hook"
        endpoint.secret = "secret"

        with (
            patch("src.services.webhook_dispatcher.validate_webhook_url", return_value=None),
            patch("src.services.webhook_dispatcher.httpx.AsyncClient") as mock_cls,
        ):
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook(delivery, endpoint)

        assert result is False
        assert delivery.last_error == "Timeout"

    @pytest.mark.asyncio
    async def test_ssrf_dead_letters_delivery(self):
        delivery = MagicMock()
        delivery.id = uuid.uuid4()
        delivery.payload = {}
        delivery.event_type = "test"
        delivery.attempt_count = 0

        endpoint = MagicMock()
        endpoint.url = "https://internal.example.com/hook"
        endpoint.secret = "secret"

        with patch(
            "src.services.webhook_dispatcher.validate_webhook_url",
            return_value="Webhook URLs must not target private or reserved IP addresses",
        ):
            result = await deliver_webhook(delivery, endpoint)

        assert result is False
        assert delivery.status == "dead_letter"
        assert delivery.next_retry_at is None
        assert "private" in delivery.last_error


class TestRetrySchedule:
    def test_retry_delays_increase(self):
        for i in range(len(RETRY_DELAYS) - 1):
            assert RETRY_DELAYS[i] < RETRY_DELAYS[i + 1]

    def test_max_attempts_matches_delays(self):
        assert MAX_ATTEMPTS == len(RETRY_DELAYS) + 1

    def test_circuit_breaker_threshold(self):
        assert CIRCUIT_BREAKER_THRESHOLD == 5
