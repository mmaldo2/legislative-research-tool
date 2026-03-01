---
status: pending
priority: p3
issue_id: "044"
tags: [code-review, quality]
dependencies: []
---

# 044 - Double-decoding risk on route parameters

## Problem Statement

Several Next.js App Router pages explicitly call `decodeURIComponent()` on route params that are already decoded by the framework. This double-decoding can corrupt values containing `%25` (a literal percent sign) or other pre-encoded sequences, leading to subtle data integrity bugs.

## Findings

- Explicit `decodeURIComponent(id)` calls found in:
  - `frontend/src/app/bills/[id]/page.tsx:19,34`
  - `frontend/src/app/legislators/[id]/page.tsx:17,32`
  - `frontend/src/app/jurisdictions/[id]/page.tsx:11`
- Next.js App Router automatically decodes dynamic route parameters before passing them to page components.
- Double-decoding example: a bill ID containing a literal `%` sign would be URL-encoded as `%25` in the URL. Next.js decodes it to `%`. The explicit `decodeURIComponent()` then attempts to decode `%` as a percent-encoded sequence, which either throws a `URIError` or produces a corrupted value.

## Proposed Solutions

1. Remove all explicit `decodeURIComponent()` calls on route params in the affected pages.
2. Use the params directly as provided by Next.js App Router.

Before:
```tsx
const decodedId = decodeURIComponent(id);
```

After:
```tsx
// Next.js App Router already decodes params
const decodedId = id;
```

## Technical Details

- Next.js App Router decodes `params` automatically. This is documented behavior and consistent across all dynamic segments (`[id]`, `[slug]`, etc.).
- The encode/decode inconsistency means that if a value is encoded once in a `<Link>` href but decoded twice on the receiving page, values with special characters will break.
- Edge case: If any upstream code double-encodes values, removing the explicit decode will surface that bug rather than masking it, which is the correct behavior.

## Acceptance Criteria

- [ ] `decodeURIComponent()` calls removed from `bills/[id]/page.tsx`
- [ ] `decodeURIComponent()` calls removed from `legislators/[id]/page.tsx`
- [ ] `decodeURIComponent()` calls removed from `jurisdictions/[id]/page.tsx`
- [ ] Pages correctly display entities with special characters in their IDs
- [ ] No `URIError` exceptions when navigating to pages with percent-encoded IDs
- [ ] `npm run build` passes with no errors

## Work Log

_No work performed yet._

## Resources

- `frontend/src/app/bills/[id]/page.tsx`
- `frontend/src/app/legislators/[id]/page.tsx`
- `frontend/src/app/jurisdictions/[id]/page.tsx`
- [Next.js Dynamic Routes Documentation](https://nextjs.org/docs/app/building-your-application/routing/dynamic-routes)
