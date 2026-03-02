---
status: complete
priority: p1
issue_id: "087"
tags: [code-review, performance]
dependencies: []
---

# N+1 query storm in alert evaluator

## Problem

`evaluate_alerts_for_changes()` has a triple-nested loop with per-iteration DB queries. For S saved searches, E events, N subscriptions: executes S + (S*E*N) queries. At 100 searches, 500 events, 3 subs = 150,102 queries.

## Files

- `src/services/alert_evaluator.py:56-96`

## Solution

Batch-load all active subscriptions and all active endpoints in 2 queries upfront, then use in-memory dict lookups in the loop. Reduces total to 4 fixed queries regardless of data volume.

## Acceptance Criteria

- `evaluate_alerts_for_changes` uses only batch queries.
- Existing tests still pass.
- New test for batch behavior.
