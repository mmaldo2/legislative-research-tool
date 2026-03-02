---
status: complete
priority: p3
issue_id: "097"
tags: [code-review, quality]
dependencies: []
---

# Missing back_populates

## Problem

SavedSearch.organization and WebhookEndpoint.organization relationships are missing back_populates="saved_searches" and back_populates="webhook_endpoints" to match the Organization model's declared back_populates targets. Bidirectional relationship sync won't work correctly in-session.

## Files

- src/models/saved_search.py:31
- src/models/webhook_endpoint.py:30

## Solution

Add back_populates parameter to both relationship declarations.
