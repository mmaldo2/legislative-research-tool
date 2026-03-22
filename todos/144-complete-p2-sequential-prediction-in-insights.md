---
status: pending
priority: p2
issue_id: 144
tags: [performance, code-review]
---

# Sequential Prediction Calls in Precedent Insights Endpoint (N+1)

## Problem Statement

The precedent insights endpoint calls `predict_bill()` and queries `ai_analyses`
per-precedent in a sequential loop, creating an N+1 pattern. With 10+ precedents this
adds multiple seconds of latency from serialized I/O.

## Findings

- Each precedent triggers an individual `predict_bill()` call.
- Each precedent triggers a separate `ai_analyses` query for its summary.
- Both operations are I/O-bound and independent across precedents, making them ideal
  candidates for batching and concurrency.

## Technical Details

**Files:**
- `src/api/policy_workspaces.py` — precedent insights handler

**Recommended fix:**
1. Batch the AI analysis summary query using a single `SELECT ... WHERE bill_id IN (...)`.
2. Parallelize `predict_bill()` calls with `asyncio.gather()` (with a concurrency cap
   via `asyncio.Semaphore` if needed to avoid overwhelming the model service).
3. Combine batched summaries and gathered predictions into the response.

## Acceptance Criteria

- [ ] AI analysis summaries fetched in a single batched query.
- [ ] Prediction calls run concurrently via `asyncio.gather()`.
- [ ] Response shape and content remain unchanged.
- [ ] Endpoint latency with 10 precedents is measurably reduced.
