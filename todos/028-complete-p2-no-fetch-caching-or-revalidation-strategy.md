---
status: complete
priority: p2
issue_id: "028"
tags: [code-review, performance]
dependencies: []
---

# 028 — No Fetch Caching or Revalidation Strategy

## Problem Statement

All fetches in the frontend use the default `cache: "no-store"` behavior (Next.js 15+ default). Data that rarely changes — jurisdictions, legislative sessions — is re-fetched from the backend on every single page load. With 100 concurrent users, this means 100 identical requests for the same jurisdiction list. There is no revalidation strategy anywhere in the codebase.

## Findings

- `fetchApi` in `frontend/src/lib/api.ts` (lines 31-44) does not pass any `next` caching options to `fetch()`.
- In Next.js 15+, the default is `cache: "no-store"`, so every call is a fresh network request.
- Jurisdictions and sessions change very infrequently (days/weeks), yet are fetched fresh on every page load.
- Search results change more frequently but could still benefit from short-lived caching.
- Bill detail pages could tolerate 5-minute staleness in most cases.
- No `revalidatePath` or `revalidateTag` calls exist anywhere in the codebase.
- The backend already has rate limiting (100 req/min), making uncached frontend calls a scaling bottleneck.

## Proposed Solutions

### Solution A: Add `next.revalidate` to fetchApi with per-endpoint configuration

Extend `fetchApi` to accept a `revalidate` option and define default revalidation intervals by endpoint pattern. Use 3600s for jurisdictions/sessions, 300s for bill detail, 60s for search results.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Straightforward to implement; leverages built-in Next.js data cache; no external dependencies; per-endpoint granularity |
| **Cons** | Requires careful choice of revalidation intervals; stale data possible within the window |
| **Effort** | Small-medium — modify fetchApi signature and update call sites with appropriate intervals |
| **Risk** | Low — data staleness is bounded and acceptable for legislative data |

### Solution B: Use Next.js tag-based revalidation with on-demand invalidation

Assign cache tags to each fetch call (e.g., `bill-{id}`, `jurisdictions`). Add revalidation API routes or server actions that call `revalidateTag()` when data is known to have changed.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Precise cache invalidation; data is always fresh when explicitly updated; combines well with webhooks |
| **Cons** | Requires additional infrastructure for invalidation triggers; more complex architecture; overkill if the backend doesn't push change notifications |
| **Effort** | Medium-large — tag assignment, revalidation routes, integration with data pipeline |
| **Risk** | Medium — complexity increase; requires coordination between backend ingestion and frontend cache |

### Recommendation

**Solution A** is the pragmatic choice. Legislative data changes infrequently enough that time-based revalidation provides excellent caching with minimal complexity. Solution B can be layered on later if real-time freshness becomes a requirement.

## Technical Details

**Current code** (`frontend/src/lib/api.ts`, approximate):
```typescript
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  // ...
}
```

**Proposed change** (Solution A):
```typescript
interface FetchApiOptions extends RequestInit {
  revalidate?: number | false;
}

async function fetchApi<T>(endpoint: string, options?: FetchApiOptions): Promise<T> {
  const { revalidate, ...fetchOptions } = options ?? {};

  const response = await fetch(`${API_URL}${endpoint}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...fetchOptions,
    next: revalidate !== undefined ? { revalidate } : undefined,
  });
  // ...
}

// Usage examples:
export async function listJurisdictions() {
  return fetchApi<Jurisdiction[]>("/jurisdictions", { revalidate: 3600 }); // 1 hour
}

export async function listSessions(jurisdiction: string) {
  return fetchApi<Session[]>(`/sessions?jurisdiction=${jurisdiction}`, { revalidate: 3600 });
}

export async function searchBills(params: SearchParams) {
  return fetchApi<SearchResult>(`/search?${qs}`, { revalidate: 60 }); // 1 minute
}

export async function getBill(id: string) {
  return fetchApi<Bill>(`/bills/${encodeURIComponent(id)}`, { revalidate: 300 }); // 5 minutes
}
```

## Acceptance Criteria

- [ ] `fetchApi` accepts an optional `revalidate` parameter that maps to `next: { revalidate }`.
- [ ] Jurisdiction and session list endpoints use `revalidate: 3600` (1 hour).
- [ ] Search endpoints use `revalidate: 60` (1 minute).
- [ ] Bill and legislator detail endpoints use `revalidate: 300` (5 minutes).
- [ ] Repeated page loads within the revalidation window do NOT trigger new backend requests.
- [ ] The Next.js data cache is functional in both development and production builds.
- [ ] No stale data issues observed in normal usage patterns.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/api.ts` — fetchApi implementation
- Next.js caching docs: https://nextjs.org/docs/app/building-your-application/caching
- Next.js fetch revalidation: https://nextjs.org/docs/app/building-your-application/data-fetching/fetching#revalidating-cached-data
