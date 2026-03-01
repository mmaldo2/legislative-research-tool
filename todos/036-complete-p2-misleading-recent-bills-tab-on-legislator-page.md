---
status: complete
priority: p2
issue_id: "036"
tags: [code-review, quality, architecture]
dependencies: []
---

# 036 — Misleading Recent Bills Tab on Legislator Page

## Problem Statement

The legislator detail page includes a "Recent Bills" tab that claims to show bills sponsored by the legislator. In reality, it shows ALL bills from the legislator's jurisdiction because the API does not support filtering by sponsor. A comment in the code acknowledges this limitation. This is actively misleading to users — they believe they are seeing a legislator's sponsored bills when they are actually seeing unrelated legislation from the same state.

## Findings

- `frontend/src/app/legislators/[id]/page.tsx` (lines 37-49) fetches bills using `listBills()` filtered only by the legislator's jurisdiction.
- A comment in the code admits: "the API doesn't have a sponsor filter."
- The tab is labeled "Recent Bills" which implies a connection to the specific legislator.
- Users will see bills the legislator had no involvement with, creating false associations.
- The backend has no `/legislators/{id}/bills` endpoint or sponsor-based bill filtering.
- This is a data integrity / trust issue — users may make incorrect conclusions about a legislator's legislative activity.

## Proposed Solutions

### Solution A: Remove the bills tab until the API supports sponsor filtering

Delete the "Recent Bills" tab entirely. The legislator page shows only the info tab with the legislator's details. The tab can be re-added once the backend supports a `sponsor` filter on the bills endpoint or a `/legislators/{id}/sponsored_bills` endpoint.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Eliminates the misleading UI; simplifies the page by ~40 lines; honest about available data |
| **Cons** | Reduces the content on the legislator page; may feel sparse |
| **Effort** | Small — delete the tab and related code |
| **Risk** | Very low — removing a misleading feature is always safer than keeping it |

### Solution B: Relabel the tab as "Jurisdiction Bills" with a disclaimer

Keep the tab but rename it from "Recent Bills" to "Jurisdiction Bills" or "Bills in [State]". Add a visible disclaimer explaining these are bills from the same jurisdiction, not bills sponsored by this legislator.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Preserves the content; sets correct user expectations; provides useful context about the jurisdiction |
| **Cons** | Still somewhat confusing — users on a legislator page expect legislator-specific data; the tab feels out of place |
| **Effort** | Small — rename the tab label and add disclaimer text |
| **Risk** | Low — but doesn't fully resolve the UX mismatch |

### Recommendation

**Solution A** is preferred. Displaying jurisdiction-wide bills on a legislator's page, even with a disclaimer, creates a confusing information architecture. It is better to show no bills than wrong bills. File a separate backlog item to add a backend sponsor-filter endpoint, then re-add the tab with correct data.

## Technical Details

**Current code** (`frontend/src/app/legislators/[id]/page.tsx`, approximate):
```typescript
// Fetch bills for the legislator's jurisdiction
// Note: the API doesn't have a sponsor filter, so this shows ALL jurisdiction bills
const jurisdiction = person.jurisdiction?.id;
let bills: Bill[] = [];
if (jurisdiction) {
  const billsResponse = await listBills({
    jurisdiction,
    per_page: 10,
  });
  bills = billsResponse.results;
}

// In the render:
<TabsTrigger value="bills">Recent Bills</TabsTrigger>
<TabsContent value="bills">
  {/* Renders bills that are NOT specific to this legislator */}
</TabsContent>
```

**Proposed change** (Solution A — remove tab):
```typescript
// Remove the listBills() call entirely
// Remove the "bills" TabsTrigger and TabsContent
// Remove the bills variable and related imports
```

**Proposed change** (Solution B — relabel):
```typescript
<TabsTrigger value="bills">
  Bills in {formatJurisdiction(person.jurisdiction?.id)}
</TabsTrigger>
<TabsContent value="bills">
  <p className="text-sm text-muted-foreground mb-4">
    These are recent bills from this legislator's jurisdiction, not bills
    they have sponsored. Sponsor filtering is not yet available.
  </p>
  {/* ... existing bill list */}
</TabsContent>
```

## Acceptance Criteria

- [ ] The legislator detail page does not display bills that are not specifically related to the legislator.
- [ ] If the tab is removed (Solution A): no "Recent Bills" tab appears; page renders correctly with remaining tabs.
- [ ] If the tab is relabeled (Solution B): the tab clearly indicates these are jurisdiction bills, not sponsored bills, with a visible disclaimer.
- [ ] A separate backlog item is created to add sponsor-based bill filtering to the backend API.
- [ ] No regression in the legislator info tab or other page functionality.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/legislators/[id]/page.tsx` — legislator detail page
- `frontend/src/lib/api.ts` — `listBills()` function
- Open States API docs: https://openstates.org/api/
