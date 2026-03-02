"""Webhook dispatcher — HMAC signing, delivery, retry with exponential backoff."""

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.webhook_delivery import WebhookDelivery
from src.models.webhook_endpoint import WebhookEndpoint

logger = logging.getLogger(__name__)

# Private/reserved IP networks that webhook URLs must not resolve to
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_webhook_url(url: str) -> str | None:
    """Validate a webhook URL is safe to deliver to.

    Returns an error message if invalid, or None if valid.
    """
    parsed = urlparse(url)

    # Enforce HTTPS only
    if parsed.scheme != "https":
        return "Webhook URLs must use HTTPS"

    if not parsed.hostname:
        return "Invalid URL: no hostname"

    # Resolve hostname and check against blocked networks
    try:
        addrs = socket.getaddrinfo(
            parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        return f"Cannot resolve hostname: {parsed.hostname}"

    for _, _, _, _, sockaddr in addrs:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                return "Webhook URLs must not target private or reserved IP addresses"

    return None

# Retry schedule in seconds: ~24 hours total coverage
# 1m, 5m, 15m, 1h, 2h, 4h, 8h, 16h
RETRY_DELAYS = [60, 300, 900, 3600, 7200, 14400, 28800, 57600]
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1  # Initial attempt + retries

# Circuit breaker: disable endpoint after N consecutive dead-letter deliveries
CIRCUIT_BREAKER_THRESHOLD = 5


def sign_payload(payload: dict, secret: str) -> dict[str, str]:
    """Sign a webhook payload with HMAC-SHA256.

    Returns headers dict with X-Webhook-Signature and X-Webhook-Timestamp.
    """
    timestamp = str(int(time.time()))
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return {
        "X-Webhook-Signature": f"t={timestamp},v1={sig}",
        "X-Webhook-Timestamp": timestamp,
    }


def verify_signature(payload: dict, secret: str, signature_header: str) -> bool:
    """Verify an incoming webhook signature (for test/documentation purposes)."""
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    timestamp = parts.get("t", "")
    expected_sig = parts.get("v1", "")

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    computed = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, expected_sig)


async def enqueue_delivery(
    session: AsyncSession,
    endpoint: WebhookEndpoint,
    event_type: str,
    payload: dict,
) -> WebhookDelivery:
    """Create a queued delivery record for a webhook endpoint."""
    delivery = WebhookDelivery(
        endpoint_id=endpoint.id,
        event_type=event_type,
        idempotency_key=f"{endpoint.id}:{event_type}:{uuid.uuid4().hex[:12]}",
        payload=payload,
        status="queued",
        next_retry_at=datetime.now(UTC),
    )
    session.add(delivery)
    return delivery


async def deliver_webhook(delivery: WebhookDelivery, endpoint: WebhookEndpoint) -> bool:
    """Attempt HTTP POST delivery. Returns True on success."""
    # SSRF check at delivery time (DNS can change after registration)
    ssrf_error = validate_webhook_url(endpoint.url)
    if ssrf_error:
        delivery.last_error = ssrf_error
        delivery.attempt_count += 1
        delivery.status = "dead_letter"
        delivery.next_retry_at = None
        return False

    headers = sign_payload(delivery.payload, endpoint.secret)
    headers["Content-Type"] = "application/json"
    headers["X-Webhook-Event"] = delivery.event_type
    headers["X-Webhook-Delivery-Id"] = str(delivery.id)

    body = json.dumps(delivery.payload, separators=(",", ":"), sort_keys=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(endpoint.url, content=body, headers=headers)
            delivery.last_status_code = resp.status_code

            if 200 <= resp.status_code < 300:
                delivery.status = "delivered"
                delivery.delivered_at = datetime.now(UTC)
                delivery.next_retry_at = None
                return True

            delivery.last_error = f"HTTP {resp.status_code}"
        except httpx.TimeoutException:
            delivery.last_error = "Timeout"
        except httpx.HTTPError as e:
            delivery.last_error = str(e)[:500]

    # Failed — schedule retry or dead-letter
    delivery.attempt_count += 1

    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = "dead_letter"
        delivery.next_retry_at = None
    else:
        delivery.status = "failed"
        delay = RETRY_DELAYS[min(delivery.attempt_count - 1, len(RETRY_DELAYS) - 1)]
        # Add jitter: +/- 20%
        jitter = secrets.randbelow(int(delay * 0.4)) - int(delay * 0.2)
        delivery.next_retry_at = datetime.now(UTC) + timedelta(seconds=delay + jitter)

    return False


async def process_delivery_queue(session: AsyncSession) -> int:
    """Poll delivery queue and attempt pending/retryable deliveries.

    Returns the number of successful deliveries.
    """
    now = datetime.now(UTC)

    # Find deliveries ready to process
    result = await session.execute(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.status.in_(["queued", "failed"]),
            WebhookDelivery.next_retry_at <= now,
        )
        .order_by(WebhookDelivery.next_retry_at)
        .limit(50)
    )
    deliveries = list(result.scalars().all())

    if not deliveries:
        return 0

    # Pre-fetch endpoints
    endpoint_ids = {d.endpoint_id for d in deliveries}
    ep_result = await session.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.id.in_(endpoint_ids))
    )
    endpoints = {ep.id: ep for ep in ep_result.scalars().all()}

    successes = 0
    for delivery in deliveries:
        endpoint = endpoints.get(delivery.endpoint_id)
        if not endpoint or not endpoint.is_active:
            delivery.status = "dead_letter"
            delivery.last_error = "Endpoint inactive or deleted"
            delivery.next_retry_at = None
            continue

        delivery.status = "attempting"
        await session.flush()

        success = await deliver_webhook(delivery, endpoint)
        if success:
            successes += 1
            # Reset failure count on success
            await session.execute(
                update(WebhookEndpoint)
                .where(WebhookEndpoint.id == endpoint.id)
                .values(failure_count=0)
            )
        else:
            # Increment failure count, check circuit breaker
            new_count = endpoint.failure_count + 1
            values: dict = {"failure_count": new_count}
            if new_count >= CIRCUIT_BREAKER_THRESHOLD:
                values["is_active"] = False
                logger.warning(
                    "Circuit breaker tripped for endpoint %s after %d failures",
                    endpoint.id,
                    new_count,
                )
            await session.execute(
                update(WebhookEndpoint).where(WebhookEndpoint.id == endpoint.id).values(**values)
            )

    await session.commit()
    logger.info("Webhook delivery: %d/%d successful", successes, len(deliveries))
    return successes
