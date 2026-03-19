---
status: pending
priority: p1
issue_id: "118"
tags: [code-review, prediction, correctness, rate-limiting]
dependencies: []
---

# Duplicate Limiter Instance — Rate Limiting by IP Instead of API Key

## Problem Statement

`src/api/prediction.py` (line 14) creates its own `Limiter(key_func=get_remote_address)` instead of using the shared limiter from `src/api/deps.py`. This is a correctness bug: the prediction endpoint rate-limits by IP address while every other endpoint rate-limits by API key hash.

## Findings

- The app-wide limiter in `deps.py` uses `_get_key_func()` which hashes the API key when present, falling back to IP.
- The prediction endpoint's separate limiter creates an independent rate-limit state store.
- Result: Multiple orgs behind the same IP share a rate limit pool; one org using multiple IPs gets 30/min per IP.
- The SlowAPI error handler references `app.state.limiter` (the deps instance), so rate limit errors from the prediction limiter may not trigger the JSON error handler correctly.

## Proposed Solutions

### Option A: Use shared limiter from deps.py (Recommended)
```python
from src.api.deps import get_session, limiter
# Remove: limiter = Limiter(key_func=get_remote_address)
```
- **Effort:** Small (1 line change)
- **Risk:** None

## Acceptance Criteria

- [ ] `src/api/prediction.py` imports `limiter` from `src.api.deps`
- [ ] No local `Limiter` instantiation in prediction.py
- [ ] Rate limit errors return JSON (not HTML)

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-18 | Created | Flagged by Security, Python, Performance, Architecture reviewers |
