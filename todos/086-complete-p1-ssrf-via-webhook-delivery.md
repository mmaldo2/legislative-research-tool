---
status: complete
priority: p1
issue_id: "086"
tags: [code-review, security]
dependencies: []
---

# SSRF via webhook delivery

## Problem

Users register webhook URLs validated only by Pydantic HttpUrl. No SSRF protection — URLs targeting internal services (169.254.169.254, 10.x, localhost) are accepted and POSTed to by the delivery system.

## Files

- `src/services/webhook_dispatcher.py:83-85`
- `src/api/webhooks.py:47`

## Solution

Add URL validation that blocks private/reserved IP ranges and enforces HTTPS-only. Validate both at registration time and at delivery time (DNS can change). Use `ipaddress` module to check resolved addresses against blocked networks.

## Acceptance Criteria

- Registration of http://169.254.169.254/... returns 422.
- HTTPS-only enforced.
- Private IP ranges blocked.
