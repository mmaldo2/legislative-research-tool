---
status: complete
priority: p1
issue_id: "085"
tags: [code-review, api, data-integrity]
dependencies: []
---

# event_types silently discarded on webhook creation

## Problem

`WebhookEndpointCreate` schema has `event_types: list[str]` field, but the API handler never reads it and the `WebhookEndpoint` model has no `event_types` column. Input is silently discarded, misleading API consumers.

## Files

- `src/schemas/webhook.py:11-14`
- `src/api/webhooks.py:44-49`

## Solution

Remove `event_types` from `WebhookEndpointCreate` since event filtering lives on `AlertSubscription`. This eliminates the misleading API contract.

## Acceptance Criteria

- `event_types` removed from WebhookEndpointCreate.
- OpenAPI spec no longer shows it.
