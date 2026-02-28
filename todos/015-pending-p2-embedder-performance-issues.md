---
status: pending
priority: p2
issue_id: "015"
tags: [code-review, performance]
dependencies: []
---

# Embedder Creates httpx Client Per Call and Flushes Per Row

## Problem Statement

`src/search/embedder.py` creates a new `httpx.AsyncClient` on every call and does `flush()` + individual `UPDATE` per row during batch embedding. This is both slow and resource-wasteful.

## Findings

- **performance-oracle**: httpx client per call, flush+SQL per row
- **kieran-python-reviewer (MEDIUM)**: Import inside loop, httpx per-call

**Affected file:** `src/search/embedder.py`

## Proposed Solutions

### Option A: Shared client + batched updates (Recommended)
- Create httpx client once (module-level or injected)
- Batch UPDATE statements using `executemany` or bulk update
- Move imports to module level
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] httpx client is reused across calls
- [ ] Batch embedding uses bulk database updates
- [ ] No imports inside loops
