---
status: complete
priority: p2
issue_id: "032"
tags: [code-review, quality]
dependencies: []
---

# 032 — Duplicated Chamber Mapping Logic

## Problem Statement

The mapping of chamber identifiers (`"upper"` to `"Senate"`, `"lower"` to `"House"`) is repeated in at least three different files across the frontend. Each copy has slightly different handling of edge cases — notably, the actions-tab implementation defaults any non-`"upper"` value to `"House"`, which incorrectly labels `"joint"`, `"legislature"`, or other chamber values. This duplication creates inconsistency bugs and maintenance burden.

## Findings

- `actions-tab.tsx` (line 33): Maps `"upper"` to `"Senate"`, everything else defaults to `"House"`. This means `"joint"` chamber actions are incorrectly labeled as `"House"`.
- `legislators-list.tsx` (line 55): Another copy of the chamber mapping logic.
- `legislators/[id]/page.tsx` (lines 69 and 111): Two more instances of the same mapping.
- No shared `formatChamber()` utility exists in `format.ts` or elsewhere.
- The Open States data model includes chamber values beyond just `"upper"` and `"lower"` — `"joint"` and `"legislature"` are valid values.
- The inconsistent fallback behavior means different parts of the UI may display different labels for the same chamber value.

## Proposed Solutions

### Solution A: Extract a `formatChamber()` utility to `format.ts`

Create a single `formatChamber(chamber: string): string` function in `frontend/src/lib/format.ts` with a proper mapping including known values and a reasonable fallback (title-case the raw value). Replace all inline mappings with calls to this function.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Single source of truth; consistent behavior everywhere; easy to extend with new chamber types; testable |
| **Cons** | Requires touching 3+ files to replace inline logic |
| **Effort** | Small — one new function, 3-4 file updates |
| **Risk** | Low — straightforward refactor with no behavior change for "upper"/"lower" cases |

### Solution B: Define a chamber enum/constant map and use it inline

Create a `CHAMBER_LABELS` constant object and import it where needed, but keep the mapping logic inline at each call site.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Consistent mapping values; less abstraction than a function |
| **Cons** | Still requires inline logic at each site; doesn't enforce consistent fallback behavior; slightly more verbose |
| **Effort** | Small — one constant, 3-4 import updates |
| **Risk** | Low — but doesn't fully solve the fallback inconsistency |

### Recommendation

**Solution A** is clearly preferable. A `formatChamber()` function encapsulates both the mapping and the fallback logic in one place, guaranteeing consistency.

## Technical Details

**Current code** (scattered across files):
```typescript
// actions-tab.tsx:33
const chamberLabel = action.chamber === "upper" ? "Senate" : "House";
// BUG: "joint" → "House"

// legislators-list.tsx:55
const chamber = legislator.chamber === "upper" ? "Senate" : "House";

// legislators/[id]/page.tsx:69
person.current_role?.chamber === "upper" ? "Senate" : "House"
```

**Proposed `formatChamber()`** (`frontend/src/lib/format.ts`):
```typescript
const CHAMBER_LABELS: Record<string, string> = {
  upper: "Senate",
  lower: "House",
  joint: "Joint",
  legislature: "Legislature",
};

export function formatChamber(chamber: string): string {
  return CHAMBER_LABELS[chamber]
    ?? chamber.charAt(0).toUpperCase() + chamber.slice(1);
}
```

**Updated usage** (all 3+ files):
```typescript
import { formatChamber } from "@/lib/format";

const chamberLabel = formatChamber(action.chamber);
```

## Acceptance Criteria

- [ ] A `formatChamber()` function exists in `frontend/src/lib/format.ts`.
- [ ] `"upper"` maps to `"Senate"`, `"lower"` maps to `"House"`, `"joint"` maps to `"Joint"`.
- [ ] Unknown chamber values produce a reasonable fallback (e.g., title-cased raw value), not a hardcoded wrong label.
- [ ] All inline chamber mapping logic in `actions-tab.tsx`, `legislators-list.tsx`, and `legislators/[id]/page.tsx` is replaced with calls to `formatChamber()`.
- [ ] Unit tests cover known values, unknown values, and edge cases (empty string, null-ish).
- [ ] No UI regression — "Senate" and "House" still display correctly for `"upper"` and `"lower"`.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/lib/format.ts` — formatting utilities
- `frontend/src/components/actions-tab.tsx` — bill actions tab
- `frontend/src/components/legislators-list.tsx` — legislator list component
- `frontend/src/app/legislators/[id]/page.tsx` — legislator detail page
- Open States chamber values: https://openstates.org/data/
