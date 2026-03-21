---
status: pending
priority: p1
issue_id: "022"
tags: [code-review, security, architecture]
dependencies: []
---

# 022 — Missing API Key Header in fetchApi

## Problem Statement

The backend (`src/api/deps.py`) requires an `X-API-Key` header on all routes except the status endpoint. The frontend's `fetchApi` helper at `frontend/src/lib/api.ts:35` only sends the `Content-Type` header. This works in development because an empty key effectively disables authentication, but it will break every authenticated API call in production once a real API key is configured.

## Findings

- `fetchApi` in `frontend/src/lib/api.ts:35` constructs requests with only `Content-Type: application/json`.
- The backend dependency in `src/api/deps.py` checks for `X-API-Key` on all routes except `/status`.
- In development, the API key environment variable is empty or unset, so the auth check is effectively a no-op.
- No `API_KEY` or `NEXT_PUBLIC_API_KEY` variable exists in `frontend/.env.example`.
- Production deployments will receive 401/403 responses on every API call.

## Proposed Solutions

### Solution A: Server-side env var with conditional header

Add an `API_KEY` environment variable (without the `NEXT_PUBLIC_` prefix) on the server side. When present, include the `X-API-Key` header in all `fetchApi` requests. Since `fetchApi` calls are made from Server Components / Route Handlers, the key stays on the server and is never shipped to the client bundle.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Simple change; key never reaches the browser; minimal code diff |
| **Cons** | Requires all API calls to originate from the server (already the case in this codebase) |
| **Effort** | Small — one file change plus env example update |
| **Risk** | Low |

### Solution B: Proxy API calls through Next.js API routes

Create Next.js API route handlers (e.g., `/api/search`, `/api/bills`) that forward requests to the backend, injecting the API key server-side. The frontend client code calls the local Next.js routes instead of the backend directly.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Completely hides backend URL and key from the client; enables additional request shaping |
| **Cons** | Adds a proxy hop and latency; more boilerplate to maintain; every new backend route needs a corresponding proxy route |
| **Effort** | Medium — new route files, refactor fetchApi callers |
| **Risk** | Low |

### Recommendation

**Solution A** is preferred. The codebase already makes API calls from Server Components, so the key is naturally server-side. Solution B adds unnecessary complexity for the current architecture.

## Technical Details

**Current code** (`frontend/src/lib/api.ts:35`, approximate):
```typescript
const response = await fetch(`${API_URL}${endpoint}`, {
  headers: {
    "Content-Type": "application/json",
  },
  ...options,
});
```

**Proposed change** (Solution A):
```typescript
const headers: Record<string, string> = {
  "Content-Type": "application/json",
};

const apiKey = process.env.API_KEY;
if (apiKey) {
  headers["X-API-Key"] = apiKey;
}

const response = await fetch(`${API_URL}${endpoint}`, {
  headers,
  ...options,
});
```

**Env example addition** (`frontend/.env.example`):
```
# API key for backend authentication (server-side only, do not prefix with NEXT_PUBLIC_)
API_KEY=
```

## Acceptance Criteria

- [ ] `fetchApi` sends `X-API-Key` header when `API_KEY` environment variable is configured.
- [ ] `API_KEY` is **not** prefixed with `NEXT_PUBLIC_` — it must not appear in the client bundle.
- [ ] `frontend/.env.example` documents the new variable.
- [ ] API calls succeed in production with a valid key configured.
- [ ] API calls continue to work in development when `API_KEY` is empty or unset.
- [ ] No API key value is visible in browser DevTools network tab or client-side JS.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/api.ts` — fetchApi implementation
- `src/api/deps.py` — backend API key dependency
- `frontend/.env.example` — environment variable documentation
- Next.js docs on environment variables: https://nextjs.org/docs/app/building-your-application/configuring/environment-variables
