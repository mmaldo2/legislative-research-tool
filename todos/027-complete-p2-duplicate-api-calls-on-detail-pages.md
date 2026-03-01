---
status: complete
priority: p2
issue_id: "027"
tags: [code-review, performance]
dependencies: []
---

# 027 — Duplicate API Calls on Detail Pages

## Problem Statement

The `generateMetadata` function and the page component both call `getBill()` / `getPerson()` for the same ID on detail pages. In Next.js 15+/16, the default fetch behavior is `cache: "no-store"`, which means these are likely two completely separate network requests to the backend for identical data. Every detail page load triggers double the necessary API traffic.

## Findings

- In `frontend/src/app/bills/[id]/page.tsx` (lines 17-19 and 34), `getBill(id)` is called once in `generateMetadata()` and again in the page component.
- In `frontend/src/app/legislators/[id]/page.tsx` (lines 17-18 and 33-34), `getPerson(id)` is called once in `generateMetadata()` and again in the page component.
- Next.js 15+ changed the default fetch caching behavior from `cache: "force-cache"` to `cache: "no-store"`, so automatic request deduplication no longer applies.
- This means every detail page load issues two identical API calls for the same resource.
- Under load, this doubles the request volume to the backend for detail page views.

## Proposed Solutions

### Solution A: Wrap API functions with React `cache()`

Use React's built-in `cache()` function to memoize API calls within a single server render pass. Create cached wrappers in `api.ts` (or a separate `cached-api.ts`) and use those in both `generateMetadata` and the page component.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Minimal code change; React-native solution; works within a single render request; no external dependencies |
| **Cons** | Only deduplicates within a single request — does not cache across users or page loads |
| **Effort** | Small — add `cache()` wrappers and update imports in 2 files |
| **Risk** | Low — `cache()` is a stable React API used for exactly this pattern |

### Solution B: Use Next.js `unstable_cache` or fetch `revalidate` options

Configure Next.js-level caching with `next: { revalidate: N }` on the fetch calls so the data is cached in the Next.js data cache and shared across requests.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Eliminates duplicate calls AND provides cross-request caching; reduces backend load significantly |
| **Cons** | Data may be stale for up to N seconds; more complex cache invalidation; `unstable_cache` API may change |
| **Effort** | Medium — requires choosing revalidation intervals and potentially adding on-demand revalidation |
| **Risk** | Medium — stale data risk; must coordinate with any write operations |

### Recommendation

**Solution A** is the immediate fix for the duplicate-call problem. Solution B should be considered alongside issue #028 (fetch caching strategy) as a broader caching layer.

## Technical Details

**Current code** (`frontend/src/app/bills/[id]/page.tsx`, approximate):
```typescript
// Called once in generateMetadata
export async function generateMetadata({ params }: Props) {
  const bill = await getBill(params.id);  // 1st API call
  return { title: bill.title };
}

// Called again in page component
export default async function BillPage({ params }: Props) {
  const bill = await getBill(params.id);  // 2nd API call (duplicate)
  // ...
}
```

**Proposed change** (Solution A — in `frontend/src/lib/api.ts` or a new `cached-api.ts`):
```typescript
import { cache } from "react";

export const getBillCached = cache((id: string) => getBill(id));
export const getPersonCached = cache((id: string) => getPerson(id));
```

**Updated page** (`frontend/src/app/bills/[id]/page.tsx`):
```typescript
import { getBillCached } from "@/lib/api";

export async function generateMetadata({ params }: Props) {
  const bill = await getBillCached(params.id);  // memoized
  return { title: bill.title };
}

export default async function BillPage({ params }: Props) {
  const bill = await getBillCached(params.id);  // returns cached result
  // ...
}
```

## Acceptance Criteria

- [ ] `getBill()` and `getPerson()` calls are deduplicated within a single page render using React `cache()`.
- [ ] `generateMetadata` and page component use the cached wrapper functions.
- [ ] Backend logs confirm only one API call per detail page load (not two).
- [ ] Page behavior and metadata generation remain functionally identical.
- [ ] No regression in detail page rendering or SEO metadata.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/bills/[id]/page.tsx` — bill detail page
- `frontend/src/app/legislators/[id]/page.tsx` — legislator detail page
- `frontend/src/lib/api.ts` — API helper functions
- React `cache()` docs: https://react.dev/reference/react/cache
- Next.js caching docs: https://nextjs.org/docs/app/building-your-application/caching
