---
status: complete
priority: p1
issue_id: "084"
tags: [code-review, security, api]
dependencies: []
---

# Webhook secret never returned to the user

## Problem

`WebhookEndpointResponse` excludes `secret`, but the `POST /webhooks` create response also uses this schema, so the signing secret is never returned to the user. They cannot verify incoming webhook signatures.

## Files

- `src/api/webhooks.py:54-61`
- `src/schemas/webhook.py`

## Solution

Create a `WebhookEndpointCreateResponse` schema that includes `secret`, use it only for the POST 201 response. This follows the pattern used by Stripe/GitHub — show secret exactly once at creation time.

## Acceptance Criteria

- POST /webhooks returns secret in response.
- GET /webhooks still omits it.
- Test confirms.
