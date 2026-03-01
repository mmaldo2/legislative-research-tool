---
status: complete
priority: p1
issue_id: "048"
tags: [code-review, frontend, quality]
dependencies: []
---

# fetchApi Crashes on 204 No Content Responses + Unsafe Header Cast

## Problem Statement

Two bugs in the frontend API client: (1) `fetchApi` always calls `res.json()` which throws `SyntaxError` on 204 No Content responses from DELETE endpoints, and (2) an unsafe `as Record<string, string>` cast on headers that silently drops `Headers` instances.

## Findings

1. `deleteCollection` and `removeFromCollection` return `Promise<void>` but `fetchApi` calls `res.json()` unconditionally — 204 responses have no body, causing runtime crash (`frontend/src/lib/api.ts` line 90)
2. `rest.headers as Record<string, string>` — spreading a `Headers` object produces an empty object, silently losing all headers (`frontend/src/lib/api.ts` line 67)
3. Agent: TypeScript Reviewer (findings #1, #2)

## Proposed Solutions

### Option A: Handle 204 + normalize headers (Recommended)
- Add `if (res.status === 204) return undefined as T` before `res.json()`
- Replace cast with a `normalizeHeaders()` helper that handles Headers, string[][], and Record
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `frontend/src/lib/api.ts`

## Acceptance Criteria

- [ ] DELETE endpoints (collections, collection items) don't throw on 204
- [ ] Headers passed as `new Headers(...)` are correctly forwarded
- [ ] Existing API calls continue working

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
