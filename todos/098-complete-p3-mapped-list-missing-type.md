---
status: complete
priority: p3
issue_id: "098"
tags: [code-review, quality]
dependencies: []
---

# Mapped[list] Missing Element Type

## Problem

AlertSubscription.event_types is `Mapped[list]` (bare list), should be `Mapped[list[str]]`. SavedSearch.criteria is `Mapped[dict]`, should be `Mapped[dict[str, Any]]`. Loses element type information.

## Files

- src/models/alert_subscription.py:29
- src/models/saved_search.py:24

## Solution

Add element type parameters to both annotations.
