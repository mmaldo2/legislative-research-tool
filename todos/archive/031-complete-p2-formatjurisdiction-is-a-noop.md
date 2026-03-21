---
status: complete
priority: p2
issue_id: "031"
tags: [code-review, quality]
dependencies: []
---

# 031 — formatJurisdiction Is a No-Op

## Problem Statement

The `formatJurisdiction` function in `frontend/src/lib/format.ts` contains a `.replace(/-/g, "-")` call that replaces hyphens with hyphens — a complete no-op. The function effectively just calls `.toUpperCase()` on the input. The replace either reflects a copy-paste error (intended to replace hyphens with spaces or something else) or is dead code that should be removed. Either way, the formatting result is poor: `"us-ca"` becomes `"US-CA"` instead of a human-readable name like `"California"`.

## Findings

- `frontend/src/lib/format.ts` (lines 4-6) defines `formatJurisdiction`.
- The `.replace(/-/g, "-")` replaces every hyphen with a hyphen — identical input and output.
- The function returns the raw jurisdiction ID in uppercase (e.g., `"US-CA"` instead of `"California"`).
- This is used in UI-facing contexts where users see jurisdiction names.
- The no-op replace strongly suggests the original intent was different (perhaps `/-/g, " "` for spaces).
- No test coverage exists for this function.

## Proposed Solutions

### Solution A: Remove the no-op and implement a proper jurisdiction display name lookup

Create a mapping of jurisdiction IDs to human-readable names (e.g., `"ocd-jurisdiction/country:us/state:ca/government"` or `"us-ca"` to `"California"`). Fall back to the uppercased ID for unknown jurisdictions.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Provides genuinely useful formatting; good UX; eliminates the confusing no-op code |
| **Cons** | Requires maintaining a jurisdiction name mapping; mapping may need to cover 50+ states plus territories |
| **Effort** | Medium — build the mapping table and update the function |
| **Risk** | Low — purely a display improvement; fallback to ID ensures nothing breaks |

### Solution B: Fix the no-op to do minimal formatting and remove dead code

Remove the `.replace(/-/g, "-")` call entirely since it does nothing. Optionally replace hyphens with spaces and title-case the result so `"us-ca"` becomes `"Us Ca"`. Minimal change, minimal effort.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Quick fix; removes the confusing no-op; marginally better display |
| **Cons** | `"Us Ca"` is still not a great jurisdiction display name; doesn't solve the underlying UX problem |
| **Effort** | Small — one-line fix |
| **Risk** | Low — trivial change |

### Recommendation

**Solution A** is the right long-term fix. If the jurisdiction ID format is consistent (e.g., Open States format), a lookup table provides clean display names. **Solution B** is acceptable as an interim fix to eliminate the dead code.

## Technical Details

**Current code** (`frontend/src/lib/format.ts`):
```typescript
export function formatJurisdiction(id: string): string {
  return id.replace(/-/g, "-").toUpperCase();
  //           ^^^^^^^^^^ no-op: replaces "-" with "-"
}
```

**Proposed change** (Solution A):
```typescript
const JURISDICTION_NAMES: Record<string, string> = {
  "us": "United States",
  "us-ca": "California",
  "us-ny": "New York",
  "us-tx": "Texas",
  // ... full list of states and territories
};

export function formatJurisdiction(id: string): string {
  return JURISDICTION_NAMES[id.toLowerCase()] ?? id.toUpperCase();
}
```

**Proposed change** (Solution B — minimal):
```typescript
export function formatJurisdiction(id: string): string {
  return id.toUpperCase(); // removed no-op .replace(/-/g, "-")
}
```

## Acceptance Criteria

- [ ] The `.replace(/-/g, "-")` no-op is removed from `formatJurisdiction`.
- [ ] The function returns a human-readable jurisdiction name when a mapping is available.
- [ ] Unknown jurisdiction IDs fall back to a reasonable formatted string (e.g., uppercased ID).
- [ ] All UI locations displaying jurisdiction names render correctly with the updated function.
- [ ] Unit tests cover the function with known IDs, unknown IDs, and edge cases.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/format.ts` — formatting utility functions
- Open States jurisdiction ID format: https://openstates.org/data/jurisdictions/
