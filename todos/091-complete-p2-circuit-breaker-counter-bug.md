---
status: complete
priority: p2
issue_id: "091"
tags: [code-review, bug]
dependencies: []
---

# Circuit Breaker Counter Bug in Delivery Queue

## Problem

In process_delivery_queue, endpoint.failure_count is fetched before the loop but updated via raw SQL UPDATE. If the same endpoint fails twice in one batch, failure_count computes as original+1 both times instead of incrementing properly. Circuit breaker may take longer to trip.

## Files

- src/services/webhook_dispatcher.py:168-179

## Solution

After each raw UPDATE, also update endpoint.failure_count on the Python object so subsequent iterations use the incremented value. Or use `WebhookEndpoint.failure_count + 1` in the SQL expression.
