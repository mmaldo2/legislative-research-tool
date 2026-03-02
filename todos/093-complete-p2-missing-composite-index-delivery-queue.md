---
status: complete
priority: p2
issue_id: "093"
tags: [code-review, performance]
dependencies: []
---

# Missing Composite Index on Delivery Queue Poll Query

## Problem

The queue poll query filters on status + next_retry_at and sorts by next_retry_at. Separate single-column indexes exist but no composite index for this query pattern.

## Files

- migrations/versions/005_add_webhook_alert_tables.py

## Solution

Add composite index `(status, next_retry_at)` on webhook_deliveries. The two individual indexes can be removed since the composite covers both.
