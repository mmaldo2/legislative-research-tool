---
status: pending
priority: p2
issue_id: "122"
tags: [code-review, prediction, performance]
dependencies: []
---

# Add TTL Cache for Bill Predictions

## Problem Statement

`predict_bill()` executes a complex SQL query and 14 model inferences on every request. Bill data changes infrequently (at most daily), yet the rate limit allows 30 requests/minute to the same bill. Performance oracle rated this P1.

## Findings

- Each request: ~5-15ms DB query + ~5-15ms inference = ~10-30ms total
- No caching layer — same bill recomputed every time
- With 50 concurrent pro clients polling 10 bills each: 500 identical cycles where 10 would suffice

## Proposed Solutions

### Option A: In-process TTL cache (Recommended)
```python
from cachetools import TTLCache

_prediction_cache: TTLCache = TTLCache(maxsize=2048, ttl=300)  # 5 min
```
- **Pros:** 10 lines, eliminates >95% redundant work, no new infrastructure
- **Cons:** Per-worker cache, not shared across processes
- **Effort:** Small
- **Risk:** Low

## Acceptance Criteria

- [ ] Repeated requests for the same bill_id within 5 minutes return cached result
- [ ] Cache has bounded size (maxsize)
- [ ] Cache does not serve stale data beyond TTL

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Performance oracle rated as highest-impact optimization |
