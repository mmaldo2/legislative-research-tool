---
status: complete
priority: p2
issue_id: "030"
tags: [code-review, architecture, quality]
dependencies: []
---

# 030 — Missing error.tsx and not-found.tsx Boundaries

## Problem Statement

The frontend has no custom `error.tsx` or `not-found.tsx` files at the app level. Unhandled exceptions show the default Next.js error page (a blank white page in production). Calls to `notFound()` show the default 404 page with no branding, navigation, or helpful context. Users who encounter errors have no way to navigate back or understand what went wrong.

## Findings

- No `error.tsx` file exists anywhere under `frontend/src/app/`.
- No `not-found.tsx` file exists anywhere under `frontend/src/app/`.
- Unhandled throws from Server Components will render the default Next.js error UI (minimal, unbranded).
- `notFound()` calls from detail pages (see issue #029) render the default Next.js 404 page.
- The default error page in production provides no navigation, no branding, and no actionable guidance.
- Once issue #029 is fixed (re-throwing non-404 errors), the lack of `error.tsx` becomes critical — unhandled errors will show the bare default error page.

## Proposed Solutions

### Solution A: Add app-level `error.tsx` and `not-found.tsx` with consistent branding

Create `frontend/src/app/error.tsx` (client component with retry button) and `frontend/src/app/not-found.tsx` (server component with navigation links). Match the existing site layout and design system.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Catches all unhandled errors; consistent UX; provides navigation back to safety; retry capability |
| **Cons** | Only catches errors at the app level — deeply nested errors still bubble up here |
| **Effort** | Small — two new files, each 30-50 lines |
| **Risk** | Low — purely additive; no existing code changes required |

### Solution B: Add route-segment-level error boundaries for granular recovery

In addition to the app-level boundaries, add `error.tsx` files to specific route segments (`bills/[id]/error.tsx`, `legislators/[id]/error.tsx`) so errors in detail pages show contextual error messages while the rest of the layout remains intact.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Granular error recovery; layout (nav, sidebar) stays visible; contextual error messages per section |
| **Cons** | More files to maintain; risk of inconsistency between error pages |
| **Effort** | Medium — app-level boundaries plus 2-4 route-level boundaries |
| **Risk** | Low — additive changes; provides defense in depth |

### Recommendation

Start with **Solution A** to establish baseline error handling. Add route-segment-level boundaries (Solution B) as a follow-up if user research shows that preserving layout context during errors is valuable.

## Technical Details

**Proposed `frontend/src/app/error.tsx`**:
```typescript
"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="text-muted-foreground">
        An unexpected error occurred. Please try again.
      </p>
      <div className="flex gap-2">
        <button onClick={reset} className="btn btn-primary">
          Try again
        </button>
        <a href="/" className="btn btn-secondary">
          Go home
        </a>
      </div>
    </div>
  );
}
```

**Proposed `frontend/src/app/not-found.tsx`**:
```typescript
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-bold">Page Not Found</h1>
      <p className="text-muted-foreground">
        The resource you're looking for doesn't exist or may have been removed.
      </p>
      <Link href="/" className="btn btn-primary">
        Return to search
      </Link>
    </div>
  );
}
```

## Acceptance Criteria

- [ ] `frontend/src/app/error.tsx` exists and renders a branded error page with a retry button.
- [ ] `frontend/src/app/not-found.tsx` exists and renders a branded 404 page with navigation.
- [ ] Unhandled server errors show the custom error page (not the default Next.js error).
- [ ] `notFound()` calls show the custom 404 page (not the default Next.js 404).
- [ ] Both pages include navigation back to the home/search page.
- [ ] Error page logs the error for debugging (client-side `console.error`).
- [ ] Both pages are visually consistent with the rest of the application.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- Next.js error handling: https://nextjs.org/docs/app/building-your-application/routing/error-handling
- Next.js not-found: https://nextjs.org/docs/app/api-reference/file-conventions/not-found
- Related: Issue #029 (all errors treated as 404)
