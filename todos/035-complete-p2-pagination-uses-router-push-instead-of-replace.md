---
status: complete
priority: p2
issue_id: "035"
tags: [code-review, quality]
dependencies: []
---

# 035 — Pagination Uses router.push Instead of router.replace

## Problem Statement

The pagination component uses `router.push()` to navigate between pages. Every page change creates a new entry in the browser history stack. A user who pages through 10 pages of search results must click the browser "Back" button 10 times to return to their previous location. This is a poor UX pattern for pagination — `router.replace()` is the standard approach because pagination changes the view of the same resource, not navigation to a different resource.

## Findings

- `frontend/src/components/pagination.tsx` (line 22) uses `router.push()` for page changes.
- Each page change adds a new history entry.
- Paging through N pages requires N "Back" clicks to return to the previous page/route.
- This is a well-known UX anti-pattern for pagination controls.
- The URL updates correctly (query params change), but the history stack bloats.
- Most pagination implementations in production Next.js apps use `router.replace()` or `<Link replace>`.

## Proposed Solutions

### Solution A: Change `router.push()` to `router.replace()`

Simple one-line change in the pagination component. Page changes update the URL without adding history entries.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Minimal change; fixes the core UX issue; standard pagination behavior |
| **Cons** | Users cannot use "Back" to return to a previous page of results (generally acceptable — pagination controls provide this) |
| **Effort** | Trivial — one-line change |
| **Risk** | Very low — standard UX pattern |

### Solution B: Replace `router.push/replace` with `<Link>` elements using the `replace` prop

Convert pagination buttons to Next.js `<Link>` components with `replace` prop. This additionally enables prefetching of adjacent pages, improving perceived performance.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Prefetching improves perceived speed; semantic HTML (links for navigation); better accessibility |
| **Cons** | Requires refactoring the pagination component from buttons to links; slightly more code change |
| **Effort** | Small — refactor pagination to use `<Link>` with proper href and `replace` prop |
| **Risk** | Low — well-established Next.js pattern |

### Recommendation

**Solution B** is the better long-term approach because it adds prefetching benefits. However, **Solution A** is an acceptable quick fix if time is constrained. Both solve the core history-bloat problem.

## Technical Details

**Current code** (`frontend/src/components/pagination.tsx:22`, approximate):
```typescript
const handlePageChange = (page: number) => {
  const params = new URLSearchParams(searchParams.toString());
  params.set("page", page.toString());
  router.push(`?${params.toString()}`);  // Adds history entry
};
```

**Proposed change** (Solution A):
```typescript
const handlePageChange = (page: number) => {
  const params = new URLSearchParams(searchParams.toString());
  params.set("page", page.toString());
  router.replace(`?${params.toString()}`);  // Replaces history entry
};
```

**Proposed change** (Solution B):
```typescript
import Link from "next/link";

function PaginationLink({ page, children }: { page: number; children: React.ReactNode }) {
  const searchParams = useSearchParams();
  const params = new URLSearchParams(searchParams.toString());
  params.set("page", page.toString());

  return (
    <Link href={`?${params.toString()}`} replace>
      {children}
    </Link>
  );
}
```

## Acceptance Criteria

- [ ] Changing pages in search results does NOT add new entries to the browser history stack.
- [ ] The URL correctly updates to reflect the current page number.
- [ ] The browser "Back" button returns to the previous route (not the previous page of results).
- [ ] Pagination controls continue to function correctly (first, prev, next, last).
- [ ] No regression in search result display when changing pages.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/components/pagination.tsx` — pagination component
- Next.js router.replace: https://nextjs.org/docs/app/api-reference/functions/use-router#routerreplace
- Next.js Link component: https://nextjs.org/docs/app/api-reference/components/link
