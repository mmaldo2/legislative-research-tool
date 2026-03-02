---
status: pending
priority: p2
issue_id: "111"
tags: [code-review, performance, architecture]
dependencies: ["107"]
---

# Release DB Session Before LLM Call + Replace MD5 with SHA-256

## Problem Statement

The `/trends/summary` endpoint holds the DB session during the LLM call (2-10 seconds), exhausting the connection pool under load. Since `generate_trend_narrative` uses `skip_store=True`, no DB access is needed during the LLM call.

Separately, `_cache_key()` uses MD5 while the rest of the codebase uses SHA-256. MD5 is a red flag for security scanners.

## Findings

- **Performance Oracle (CRITICAL)**: Connection pool exhaustion. Default pool = 5 connections + 10 overflow. 5 concurrent summary requests saturate the pool.
- **Performance Oracle**: LLM narrative has no result caching (`skip_store=True`). Every identical request re-runs 3 queries + LLM.
- **Python Reviewer (MEDIUM)**: MD5 inconsistent with SHA-256 used elsewhere.
- **Security Sentinel (MEDIUM)**: MD5 for cache keys is a red flag.

**Affected files:**
- `src/api/trends.py` lines 190-226
- `src/services/trend_service.py` lines 31-34

## Proposed Solutions

### Option A: Release session + SHA-256 + narrative caching (Recommended)
1. After running 3 queries, close the session before calling LLM
2. Replace `hashlib.md5` with `hashlib.sha256` (truncated to 16 chars)
3. Cache narrative results in the TTL cache with longer TTL (15 min)
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] DB session released before LLM call in summary endpoint
- [ ] `_cache_key` uses SHA-256 instead of MD5
- [ ] LLM narrative results cached in TTL cache
- [ ] Comment explaining why queries are sequential (shared AsyncSession)
