---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, security, performance]
dependencies: ["001"]
---

# No Rate Limiting on API

## Problem Statement

No rate limiting exists on any endpoint. The analysis endpoints call external paid APIs (Anthropic, Voyage) — without rate limits, a single client can exhaust API budgets or cause upstream throttling that degrades service for all users.

## Findings

- **security-sentinel (C3)**: No rate limiting anywhere
- **agent-native-reviewer**: No rate limiting info exposed to clients
- **performance-oracle**: Unbounded request throughput to expensive backends

**Affected files:** `src/api/app.py`, all route files

## Proposed Solutions

### Option A: slowapi / Token Bucket (Recommended)
- Add `slowapi` dependency (FastAPI-compatible rate limiter)
- Configure per-endpoint limits: generous for reads, strict for analysis
- Example: 100 req/min for reads, 10 req/min for analysis
- **Effort**: Small
- **Risk**: Low

### Option B: Redis-backed rate limiter
- Use Redis for distributed rate limiting
- **Effort**: Medium (adds Redis dependency)
- **Risk**: Low

## Acceptance Criteria

- [ ] Analysis endpoints have strict rate limits (e.g., 10/min)
- [ ] Read endpoints have reasonable rate limits (e.g., 100/min)
- [ ] Rate limit headers returned in responses (X-RateLimit-*)
- [ ] 429 response with clear message when exceeded
