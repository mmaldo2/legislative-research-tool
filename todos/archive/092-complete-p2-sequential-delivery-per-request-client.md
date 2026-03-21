---
status: complete
priority: p2
issue_id: "092"
tags: [code-review, performance]
dependencies: []
---

# Sequential Delivery with Per-Request HTTP Client

## Problem

Each webhook delivery creates a new httpx.AsyncClient (TCP+TLS handshake overhead). Deliveries processed sequentially -- 50 deliveries with 30s timeout = 25 min worst case per batch.

## Files

- src/services/webhook_dispatcher.py:83-85
- src/services/webhook_dispatcher.py:157

## Solution

Create a single shared AsyncClient in process_delivery_queue, pass it to deliver_webhook. Group deliveries by endpoint for connection reuse. Consider asyncio.gather with semaphore for parallel delivery to different endpoints.
