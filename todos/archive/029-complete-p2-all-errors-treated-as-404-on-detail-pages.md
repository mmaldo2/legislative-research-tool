---
status: complete
priority: p2
issue_id: "029"
tags: [code-review, architecture, quality]
dependencies: []
---

# 029 — All Errors Treated as 404 on Detail Pages

## Problem Statement

Detail pages for bills and legislators use a blanket `catch { notFound() }` pattern that converts every error into a 404 response. If the backend returns a 500 Internal Server Error, a 401 Unauthorized, or a network timeout, the user sees a "Not Found" page instead of an appropriate error message. This masks real failures and makes debugging production issues significantly harder.

## Findings

- `frontend/src/app/bills/[id]/page.tsx` (lines 35-37) wraps the entire data fetch in a try/catch that calls `notFound()` on any error.
- `frontend/src/app/legislators/[id]/page.tsx` (lines 33-35) uses the identical pattern.
- The `fetchApi` helper in `api.ts` throws an error for non-OK responses, but the error object does not carry the HTTP status code in a structured way.
- There is no `ApiError` class or similar typed error that would allow distinguishing between error types.
- A 500 from the backend, a network failure, or a JSON parse error would all result in a 404 page.
- This makes it impossible for users to know whether a bill genuinely doesn't exist or the system is broken.

## Proposed Solutions

### Solution A: Create an `ApiError` class and check status before calling `notFound()`

Define a custom `ApiError` class in `api.ts` that carries the HTTP status code. In the catch block, check `err instanceof ApiError && err.status === 404` before calling `notFound()`. Re-throw all other errors so they bubble up to the nearest `error.tsx` boundary.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Clean separation of 404 vs. other errors; enables proper error UI; minimal refactoring |
| **Cons** | Requires adding an `error.tsx` boundary (see issue #030) for non-404 errors to render properly |
| **Effort** | Small — define ApiError class, update throw in fetchApi, update 2 catch blocks |
| **Risk** | Low — straightforward refactor; improves correctness |

### Solution B: Use Next.js error handling with `redirect()` for specific error codes

Instead of throwing, have `fetchApi` return a result-or-error union type. Use Next.js `redirect()` for auth errors (401/403) and let 500s propagate naturally.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | More granular error handling; can redirect to login page for auth failures |
| **Cons** | Requires changing the return type of all API functions; larger refactor |
| **Effort** | Medium — affects every API call site |
| **Risk** | Medium — broader change surface increases chance of introducing bugs |

### Recommendation

**Solution A** is the right approach. It's a focused fix that correctly distinguishes 404 from other errors with minimal code change. Pair it with issue #030 (adding error.tsx boundaries) for complete error handling.

## Technical Details

**Current code** (`frontend/src/app/bills/[id]/page.tsx`, approximate):
```typescript
export default async function BillPage({ params }: Props) {
  try {
    const bill = await getBill(params.id);
    // ... render
  } catch {
    notFound(); // ALL errors become 404
  }
}
```

**Proposed ApiError class** (`frontend/src/lib/api.ts`):
```typescript
export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message?: string,
  ) {
    super(message ?? `API error: ${status} ${statusText}`);
    this.name = "ApiError";
  }
}

// In fetchApi:
if (!response.ok) {
  throw new ApiError(response.status, response.statusText);
}
```

**Updated catch block** (`frontend/src/app/bills/[id]/page.tsx`):
```typescript
export default async function BillPage({ params }: Props) {
  try {
    const bill = await getBill(params.id);
    // ... render
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    throw err; // Re-throw 500s, network errors, etc. to error.tsx
  }
}
```

## Acceptance Criteria

- [ ] An `ApiError` class exists in `frontend/src/lib/api.ts` that carries the HTTP status code.
- [ ] `fetchApi` throws `ApiError` with the correct status code for non-OK responses.
- [ ] Detail page catch blocks only call `notFound()` for 404 errors.
- [ ] 500 errors from the backend propagate to the error boundary (not shown as 404).
- [ ] Network failures propagate to the error boundary (not shown as 404).
- [ ] Genuine 404 responses still correctly show the not-found page.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/bills/[id]/page.tsx` — bill detail page
- `frontend/src/app/legislators/[id]/page.tsx` — legislator detail page
- `frontend/src/lib/api.ts` — fetchApi implementation
- Next.js error handling: https://nextjs.org/docs/app/building-your-application/routing/error-handling
- Related: Issue #030 (missing error.tsx boundaries)
