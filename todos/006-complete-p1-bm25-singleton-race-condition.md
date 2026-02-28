---
status: pending
priority: p1
issue_id: "006"
tags: [code-review, performance, architecture]
dependencies: []
---

# BM25 Singleton Race Condition

## Problem Statement

`src/search/engine.py` uses a module-level `_bm25_index = BM25Index()` singleton. If two requests trigger `build()` concurrently, the index state is corrupted. The index also becomes stale after new ingestion runs.

## Findings

- **kieran-python-reviewer (HIGH)**: No locking on singleton build
- **performance-oracle**: Race condition on concurrent builds
- **architecture-strategist**: Module-level mutable state is dangerous

**Affected files:**
- `src/search/engine.py` — module-level singleton
- `src/search/bm25.py` — `build()` mutates instance state

## Proposed Solutions

### Option A: asyncio.Lock + build-once pattern (Recommended)
- Add `asyncio.Lock` around build
- Use `_built` flag to prevent redundant rebuilds
- Add `invalidate()` method called after ingestion
- **Effort**: Small
- **Risk**: Low

### Option B: Read-copy-update pattern
- Build new index, then atomically swap reference
- Never mutate existing index
- **Effort**: Medium
- **Risk**: Low

## Acceptance Criteria

- [ ] Concurrent `build()` calls don't corrupt index
- [ ] Index is rebuilt after ingestion completes
- [ ] Lock prevents duplicate builds
