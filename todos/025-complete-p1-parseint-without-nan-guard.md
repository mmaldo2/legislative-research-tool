---
status: pending
priority: p1
issue_id: "025"
tags: [code-review, security, typescript]
dependencies: []
---

# 025 — parseInt Without NaN Guard on Page Parameters

## Problem Statement

Three pages use `parseInt(params.page, 10)` to parse pagination parameters from URL query strings without checking for `NaN` or negative values. When a user navigates to a URL like `/search?page=abc`, `parseInt("abc")` returns `NaN`, which is then passed directly to the API as the page number. This affects three locations across the frontend.

## Findings

- **`frontend/src/app/search/page.tsx:20`** — `parseInt(searchParams.page, 10)` with no NaN check.
- **`frontend/src/app/legislators/page.tsx:20`** — same pattern, no NaN check.
- **`frontend/src/app/jurisdictions/page.tsx:17`** — same pattern, no NaN check.
- `parseInt("abc", 10)` returns `NaN`. `parseInt("-5", 10)` returns `-5`. Both are invalid page numbers.
- The `|| 1` fallback used in some locations does not catch `NaN` correctly in all cases (e.g., `parseInt("0", 10) || 1` returns `1`, which is correct by accident, but the intent is unclear).
- No upper bound is enforced on page numbers, allowing requests like `?page=999999999`.

## Proposed Solutions

### Solution A: Inline NaN/bounds check at each location

Add a guard at each of the three `parseInt` call sites to check for `NaN`, negative values, and optionally an upper bound.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Quick to implement; no new files or abstractions |
| **Cons** | Duplicated logic in three files; easy to miss a location or introduce inconsistency on future pages |
| **Effort** | Small — 3-4 lines added at each location |
| **Risk** | None |

### Solution B: Extract `parsePageParam()` utility (Recommended)

Create a shared `parsePageParam()` function in `lib/format.ts` or a new `lib/params.ts` module. All three pages import and use this single function. This is the DRY approach and pairs well with issue #024's `parseSearchParams` utility.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Single source of truth; consistent behavior across all pages; easy to unit test; pairs with #024 |
| **Cons** | Adds a small abstraction (justified given 3+ call sites) |
| **Effort** | Small — new utility function plus 3 import changes |
| **Risk** | None |

### Recommendation

**Solution B** is recommended. With three call sites today and likely more as the app grows, a shared utility is the right call. If issue #024 creates a `lib/params.ts` module, `parsePageParam` fits naturally alongside `parseSearchParams`.

## Technical Details

**Current code** (pattern repeated in 3 files):
```typescript
const page = parseInt(searchParams.page as string, 10) || 1;
```

**Proposed utility** (`lib/params.ts`):
```typescript
const MAX_PAGE = 10_000;

export function parsePageParam(
  raw: string | string[] | undefined,
  defaultPage = 1
): number {
  const parsed = parseInt(String(raw ?? ""), 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return defaultPage;
  }
  return Math.min(parsed, MAX_PAGE);
}
```

**Updated call sites** (all 3 pages):
```typescript
import { parsePageParam } from "@/lib/params";

// replaces: const page = parseInt(searchParams.page as string, 10) || 1;
const page = parsePageParam(searchParams.page);
```

**Edge cases handled:**
| Input | `parseInt` alone | With `parsePageParam` |
|-------|------------------|-----------------------|
| `"abc"` | `NaN` | `1` |
| `"-5"` | `-5` | `1` |
| `"0"` | `0` (falsy, `\|\| 1` saves it) | `1` |
| `"999999999"` | `999999999` | `10000` |
| `undefined` | `NaN` | `1` |
| `"3"` | `3` | `3` |

## Acceptance Criteria

- [ ] Non-numeric page values (e.g., `"abc"`, `undefined`) default to `1`.
- [ ] Negative page values default to `1`.
- [ ] Zero page values default to `1`.
- [ ] An upper bound is enforced (e.g., max 10,000) to prevent unreasonable API requests.
- [ ] All three affected pages use the same validation logic (no duplication).
- [ ] Unit tests cover the edge cases listed in the table above.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/search/page.tsx:20` — affected location
- `frontend/src/app/legislators/page.tsx:20` — affected location
- `frontend/src/app/jurisdictions/page.tsx:17` — affected location
- Related: Issue #024 (unsafe type assertion) — can share `lib/params.ts` module
- MDN parseInt documentation: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/parseInt
