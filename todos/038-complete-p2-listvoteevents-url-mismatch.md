---
status: complete
priority: p2
issue_id: "038"
tags: [code-review, quality]
dependencies: []
---

# 038 — listVoteEvents URL Mismatch

## Problem Statement

The frontend's `listVoteEvents()` function calls `/votes` as a top-level endpoint, but the backend expects votes to be nested under bills: `/bills/{bill_id}/votes`. If this function were ever called, it would receive a 404 response. The function is currently unused, but it represents a latent bug that will surface as soon as vote display functionality is implemented.

## Findings

- `frontend/src/lib/api.ts` (lines 125-131) defines `listVoteEvents()` which calls `fetchApi("/votes", ...)`.
- The backend routes votes as a nested resource under bills: `/bills/{bill_id}/votes`.
- There is no top-level `/votes` endpoint on the backend.
- The function does not accept a `bill_id` parameter.
- The function is currently unused in any component or page — a grep confirms no import or call site.
- This will immediately 404 when someone tries to use it.
- The function signature and URL both need updating to match the backend contract.

## Proposed Solutions

### Solution A: Fix the URL and add the required `bill_id` parameter

Update `listVoteEvents()` to accept a `bill_id` parameter and construct the correct nested URL: `/bills/${encodeURIComponent(bill_id)}/votes`.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Fixes the latent bug; matches backend API contract; ready for use when vote UI is built |
| **Cons** | Changes the function signature (breaking if anything used it, but nothing does) |
| **Effort** | Small — update function signature and URL in one place |
| **Risk** | Very low — function is unused; fixing it now prevents a bug later |

### Solution B: Remove the unused function entirely

Delete `listVoteEvents()` since it's unused and broken. Re-implement it correctly when vote display is actually needed.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Removes dead code; no risk of someone using a broken function; follows YAGNI principle |
| **Cons** | Loses the function as a reference point; will need to be re-written later |
| **Effort** | Trivial — delete the function |
| **Risk** | Very low — nothing depends on it |

### Recommendation

**Solution A** is preferred. The function represents a real API capability that will be needed. Fixing it now is trivial and prevents someone from using the broken version later without realizing the URL is wrong.

## Technical Details

**Current code** (`frontend/src/lib/api.ts`, approximate):
```typescript
export async function listVoteEvents(params?: {
  jurisdiction?: string;
  session?: string;
  page?: number;
  per_page?: number;
}) {
  const searchParams = new URLSearchParams();
  // ... param building
  return fetchApi<PaginatedResponse<VoteEvent>>(`/votes?${searchParams.toString()}`);
  //                                              ^^^^^^ WRONG: should be /bills/{bill_id}/votes
}
```

**Proposed change** (Solution A):
```typescript
export async function listVoteEvents(
  billId: string,
  params?: {
    page?: number;
    per_page?: number;
  }
) {
  const searchParams = new URLSearchParams();
  if (params?.page) searchParams.set("page", params.page.toString());
  if (params?.per_page) searchParams.set("per_page", params.per_page.toString());

  const query = searchParams.toString();
  const url = `/bills/${encodeURIComponent(billId)}/votes${query ? `?${query}` : ""}`;
  return fetchApi<PaginatedResponse<VoteEvent>>(url);
}
```

## Acceptance Criteria

- [ ] `listVoteEvents()` requires a `bill_id` parameter.
- [ ] The function constructs the URL as `/bills/{bill_id}/votes`.
- [ ] The `bill_id` is properly encoded with `encodeURIComponent()`.
- [ ] Optional pagination parameters (page, per_page) are still supported.
- [ ] The function's TypeScript types match the backend response schema.
- [ ] If Solution B is chosen: the function is fully removed with no remaining references.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/api.ts` — API helper functions
- Backend vote routes (check `src/api/` for the bills votes endpoint)
- Related: Issue #014 (missing API endpoints)
