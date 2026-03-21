---
status: pending
priority: p1
issue_id: "024"
tags: [code-review, security, typescript]
dependencies: []
---

# 024 — Unsafe Type Assertion on Search Mode Parameter

## Problem Statement

The search page at `frontend/src/app/search/page.tsx:39` uses a raw TypeScript type assertion (`mode as "keyword" | "semantic" | "hybrid"`) with no runtime validation. A user can navigate to `/search?mode=evil` and the invalid value is passed directly to the backend API. Additionally, there is no length constraint on the `q` search parameter, which was flagged as item M1 in the security review.

## Findings

- `search/page.tsx:39` performs `mode as "keyword" | "semantic" | "hybrid"` — this is a compile-time-only assertion that provides zero runtime safety.
- Any arbitrary string in the `mode` query parameter is forwarded to the backend API as-is.
- The backend may reject invalid modes with a 422, but the frontend should validate before sending to avoid unnecessary API calls and provide better UX.
- The `q` parameter at `search/page.tsx:19-20` has no `maxLength` validation; extremely long strings could be sent to the API.
- The search form component at `search-form.tsx` also lacks input length constraints on the text field.

## Proposed Solutions

### Solution A: Inline validation with allowed-values array

Define a `VALID_MODES` array and validate the `mode` parameter against it. If invalid, fall back to `"hybrid"`. Add a `maxLength` check on the `q` parameter.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Simple, self-contained, easy to review; directly addresses the issue |
| **Cons** | Validation logic is local to this one page; if other pages need similar validation, it would be duplicated |
| **Effort** | Small — a few lines in one file plus a maxLength attribute on the input |
| **Risk** | None |

### Solution B: Extract a `parseSearchParams` utility

Create a dedicated utility function (e.g., in `lib/params.ts`) that validates and sanitizes all search-related query parameters — `mode`, `q`, `page`, etc. — in a single place. Use this utility in `search/page.tsx` and any other page that handles search parameters.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | DRY; centralizes all search param validation; easy to add new params later; pairs well with issue #025 |
| **Cons** | Slightly more upfront work to extract the utility |
| **Effort** | Small — new utility file plus refactor of call sites |
| **Risk** | None |

### Recommendation

**Solution B** is preferred. Extracting a `parseSearchParams` utility creates a single source of truth for search parameter validation and pairs naturally with issue #025 (parseInt NaN guard). Both issues can share the same utility module.

## Technical Details

**Current code** (`search/page.tsx:19-20,39`, approximate):
```typescript
const q = searchParams.q as string || "";
const page = parseInt(searchParams.page as string, 10) || 1;
// ...
const mode = (searchParams.mode as "keyword" | "semantic" | "hybrid") || "hybrid";
```

**Proposed change** (Solution B — `lib/params.ts`):
```typescript
const VALID_MODES = ["keyword", "semantic", "hybrid"] as const;
type SearchMode = (typeof VALID_MODES)[number];

const MAX_QUERY_LENGTH = 500;

export function parseSearchParams(searchParams: Record<string, string | undefined>) {
  const q = (searchParams.q ?? "").slice(0, MAX_QUERY_LENGTH);

  const rawMode = searchParams.mode;
  const mode: SearchMode = VALID_MODES.includes(rawMode as SearchMode)
    ? (rawMode as SearchMode)
    : "hybrid";

  const rawPage = parseInt(searchParams.page ?? "", 10);
  const page = Number.isNaN(rawPage) || rawPage < 1 ? 1 : rawPage;

  return { q, mode, page };
}
```

**Search form input** (`search-form.tsx`):
```tsx
<input
  type="text"
  name="q"
  maxLength={500}
  // ... existing props
/>
```

## Acceptance Criteria

- [ ] Invalid `mode` values (anything other than `"keyword"`, `"semantic"`, `"hybrid"`) fall back to `"hybrid"`.
- [ ] The `q` search parameter is capped at a reasonable maximum length (e.g., 500 characters).
- [ ] The search form input element has a `maxLength` attribute matching the server-side cap.
- [ ] No raw type assertions (`as`) are used on user-supplied query parameters without runtime validation.
- [ ] The validation logic is tested (unit test for the utility function).

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/search/page.tsx` — search page with unsafe assertion
- `frontend/src/app/search/search-form.tsx` — search form component
- Related: Issue #025 (parseInt NaN guard) — can share the same utility
- TypeScript handbook on type assertions: https://www.typescriptlang.org/docs/handbook/2/everyday-types.html#type-assertions
