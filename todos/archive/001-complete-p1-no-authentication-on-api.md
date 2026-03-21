---
status: pending
priority: p1
issue_id: "001"
tags: [code-review, security]
dependencies: []
---

# No Authentication on API Endpoints

## Problem Statement

The entire API is publicly accessible with no authentication or authorization. The `/api/v1/analyze/summarize` and `/api/v1/analyze/classify` endpoints call the Anthropic API, which costs money per request. Any anonymous user can trigger unlimited LLM calls, creating a direct financial DoS vector.

## Findings

- **security-sentinel (C2)**: No authentication mechanism exists anywhere in the API
- **kieran-python-reviewer**: Analysis endpoints are unprotected
- **agent-native-reviewer**: No auth headers, API keys, or session tokens required

**Affected files:**
- `src/api/app.py` — No auth middleware
- `src/api/analysis.py` — Unprotected LLM-calling endpoints
- All route files — No dependency injection for auth

## Proposed Solutions

### Option A: API Key Authentication (Recommended for MVP)
- Add `X-API-Key` header requirement via FastAPI `Depends`
- Store valid keys in environment variable or database
- **Pros**: Simple, fast to implement, standard pattern
- **Cons**: No user-level granularity
- **Effort**: Small
- **Risk**: Low

### Option B: JWT/OAuth2
- Implement full auth flow with token refresh
- **Pros**: User-level auth, industry standard
- **Cons**: Significant complexity for MVP
- **Effort**: Large
- **Risk**: Medium (complexity)

### Option C: Auth on Analysis Endpoints Only
- Protect only the cost-generating endpoints, leave read endpoints open
- **Pros**: Minimal change, addresses financial risk
- **Cons**: Data endpoints remain unprotected
- **Effort**: Small
- **Risk**: Low

## Recommended Action

Option A for MVP — API key auth on all endpoints with Option C as an interim measure if speed is critical.

## Acceptance Criteria

- [ ] All API endpoints require authentication
- [ ] Analysis endpoints (LLM-calling) are protected from anonymous access
- [ ] Invalid/missing auth returns 401 with clear error message
- [ ] Auth mechanism documented in API docs

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from Phase 1 code review | 6 agents flagged this independently |
