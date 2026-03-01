---
status: complete
priority: p2
issue_id: "034"
tags: [code-review, quality, performance]
dependencies: []
---

# 034 — Content-Type application/json on GET Requests

## Problem Statement

The `fetchApi` helper sets `Content-Type: application/json` on every request, including GET requests that have no body. This is semantically incorrect — GET requests should not declare a content type since they carry no payload. More importantly, setting `Content-Type` on a cross-origin GET request can trigger an unnecessary CORS preflight (OPTIONS request), doubling the latency for every API call that would otherwise be a "simple request."

## Findings

- `frontend/src/lib/api.ts` (line 35) unconditionally sets `headers: { "Content-Type": "application/json" }` on all requests.
- All current API calls in the frontend are GET requests (search, list, detail fetches).
- Per the CORS specification, a GET request with `Content-Type: application/json` is NOT a "simple request" and requires a preflight OPTIONS request.
- A "simple request" (GET with no custom headers, or with only `Content-Type` set to `application/x-www-form-urlencoded`, `multipart/form-data`, or `text/plain`) skips the preflight entirely.
- Each preflight adds a full round-trip to the API server before the actual request can be made.
- The backend already has CORS configured, so preflights succeed — but they add unnecessary latency.

## Proposed Solutions

### Solution A: Only set Content-Type when the request has a body

Conditionally include the `Content-Type: application/json` header only for methods that send a body (POST, PUT, PATCH). For GET and DELETE (without body), omit the header entirely.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Semantically correct; eliminates unnecessary CORS preflights; reduces latency for all GET calls |
| **Cons** | Requires checking the method in fetchApi |
| **Effort** | Small — a few lines of conditional logic in one function |
| **Risk** | Low — removing an unnecessary header from GET requests cannot break anything |

### Solution B: Move Content-Type to the caller for non-GET requests

Remove the default Content-Type header entirely from `fetchApi`. Callers that send a body (POST/PUT) pass the header explicitly in their options. GET callers don't need to think about it.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Clean separation; fetchApi stays minimal; callers are explicit about their needs |
| **Cons** | Easy to forget the header when adding new POST endpoints; more verbose call sites |
| **Effort** | Small — remove default header, update any existing POST callers (currently none) |
| **Risk** | Low — but slightly higher risk of forgetting Content-Type on future POST calls |

### Recommendation

**Solution A** is the better approach. It's a single centralized check that automatically does the right thing for all methods, current and future.

## Technical Details

**Current code** (`frontend/src/lib/api.ts:35`, approximate):
```typescript
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",  // Set on ALL requests, including GET
    },
    ...options,
  });
  // ...
}
```

**Proposed change** (Solution A):
```typescript
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const method = options?.method?.toUpperCase() ?? "GET";
  const headers: Record<string, string> = {};

  // Only set Content-Type for methods that send a body
  if (method !== "GET" && method !== "HEAD") {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...headers,
      ...options?.headers,
    },
  });
  // ...
}
```

**CORS impact**: With this fix, cross-origin GET requests become "simple requests" that skip the preflight, saving one round-trip per API call.

## Acceptance Criteria

- [ ] GET requests from `fetchApi` do NOT include a `Content-Type` header.
- [ ] POST, PUT, and PATCH requests from `fetchApi` still include `Content-Type: application/json`.
- [ ] Cross-origin GET requests no longer trigger CORS preflight OPTIONS requests.
- [ ] All existing API calls continue to function correctly.
- [ ] Browser DevTools network tab confirms no preflight for GET calls.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/api.ts` — fetchApi implementation
- MDN CORS simple requests: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#simple_requests
- MDN Preflight requests: https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#preflighted_requests
- Fetch spec Content-Type: https://developer.mozilla.org/en-US/docs/Web/API/Request/headers
