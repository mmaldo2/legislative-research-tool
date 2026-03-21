---
status: complete
priority: p2
issue_id: "094"
tags: [code-review, api]
dependencies: []
---

# Missing CRUD Endpoints for Webhooks and Saved Searches

## Problem

Several CRUD operations are missing: GET single webhook, GET single saved search, PATCH webhook (for reactivation after circuit breaker), list/delete alert subscriptions. Once circuit breaker trips, no programmatic way to re-enable endpoint.

## Files

- src/api/webhooks.py
- src/api/saved_searches.py

## Solution

Add GET /webhooks/{id}, GET /saved-searches/{id}, PATCH /webhooks/{id} (support is_active), GET /saved-searches/{id}/alerts, DELETE /saved-searches/{id}/alerts/{sub_id}.
