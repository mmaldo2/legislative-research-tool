---
status: complete
priority: p2
issue_id: "037"
tags: [code-review, performance]
dependencies: []
---

# 037 — Sequential Waterfall on Legislator Detail Page

## Problem Statement

The legislator detail page fetches data sequentially: `getPerson()` completes first, then `listBills()` starts. Neither fetch is wrapped in a Suspense boundary. If the person API call takes 100ms and the bills API call takes 150ms, the user waits 250ms before seeing anything. The person header and the bills tab could load independently, with the bills section streaming in after the header renders.

## Findings

- `frontend/src/app/legislators/[id]/page.tsx` (lines 30-49) awaits `getPerson()` before calling `listBills()`.
- The `listBills()` call depends on `person.jurisdiction.id`, which creates a genuine data dependency — the jurisdiction ID is needed to fetch bills.
- However, the person header could render immediately while bills load asynchronously.
- No `<Suspense>` boundaries exist on this page.
- No loading states or skeleton UI exist for the bills section.
- The sequential waterfall adds the full latency of both calls before any content renders.
- The same pattern may apply to the bills detail page if it has multiple data fetches.

## Proposed Solutions

### Solution A: Split bills into a Suspense-wrapped async Server Component

Extract the bills section into a separate async Server Component that receives the jurisdiction ID as a prop. Wrap it in `<Suspense>` with a loading fallback. The person header renders immediately while bills stream in.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Person header renders immediately; bills stream in as they load; native React/Next.js streaming pattern; better perceived performance |
| **Cons** | Requires splitting the page into multiple components; slightly more complex component structure |
| **Effort** | Medium — extract bills section to new component, add Suspense boundary with fallback |
| **Risk** | Low — well-established Next.js streaming pattern |

### Solution B: Use `Promise.all` to parallelize the initial fetches

Since the bills fetch depends on the jurisdiction ID from the person fetch, true parallelization is not possible without a separate endpoint. However, if a `/legislators/{id}/bills` endpoint existed, both calls could run in parallel via `Promise.all`.

| Dimension | Assessment |
|-----------|------------|
| **Pros** | Reduces total wait time to max(person, bills) instead of person + bills |
| **Cons** | Requires a new backend endpoint; doesn't help with the current API design where bills need jurisdiction from person |
| **Effort** | Large — backend endpoint + frontend refactor |
| **Risk** | Medium — new endpoint needs design, testing, documentation |

### Recommendation

**Solution A** is the right approach with the current API design. The person header renders instantly, and the bills section streams in asynchronously. This directly improves perceived performance without any backend changes.

## Technical Details

**Current code** (`frontend/src/app/legislators/[id]/page.tsx`, approximate):
```typescript
export default async function LegislatorPage({ params }: Props) {
  const person = await getPerson(params.id);  // Wait 100ms

  const jurisdiction = person.jurisdiction?.id;
  let bills: Bill[] = [];
  if (jurisdiction) {
    const billsResponse = await listBills({ jurisdiction, per_page: 10 });  // Wait 150ms
    bills = billsResponse.results;
  }
  // Total: 250ms before ANY content renders

  return (
    <div>
      <PersonHeader person={person} />
      <BillsTab bills={bills} />
    </div>
  );
}
```

**Proposed change** (Solution A):
```typescript
// frontend/src/app/legislators/[id]/page.tsx
import { Suspense } from "react";
import { LegislatorBills } from "./legislator-bills";

export default async function LegislatorPage({ params }: Props) {
  const person = await getPerson(params.id);  // Wait 100ms, then render header

  return (
    <div>
      <PersonHeader person={person} />
      <Suspense fallback={<BillsTabSkeleton />}>
        <LegislatorBills jurisdictionId={person.jurisdiction?.id} />
      </Suspense>
    </div>
  );
}

// frontend/src/app/legislators/[id]/legislator-bills.tsx
export async function LegislatorBills({ jurisdictionId }: { jurisdictionId?: string }) {
  if (!jurisdictionId) return null;

  const billsResponse = await listBills({ jurisdiction: jurisdictionId, per_page: 10 });

  return <BillsTab bills={billsResponse.results} />;
}
```

**Render timeline improvement**:
- Before: `[--- person 100ms ---][--- bills 150ms ---] → 250ms to first paint`
- After: `[--- person 100ms ---] → header paints → [--- bills 150ms ---] → bills stream in`

## Acceptance Criteria

- [ ] The legislator header/info renders without waiting for the bills data to load.
- [ ] The bills section is wrapped in a `<Suspense>` boundary with a loading fallback (skeleton or spinner).
- [ ] Bills data streams in and replaces the fallback once loaded.
- [ ] Page behavior is functionally identical — same data displayed once fully loaded.
- [ ] No layout shift when bills data loads (fallback matches final layout dimensions).
- [ ] Error in bills fetch does not prevent the person header from rendering.

## Work Log

| Date | Author | Notes |
|------|--------|-------|
| 2026-02-28 | — | Issue created from PR #5 code review |

## Resources

- PR #5 code review findings
- `frontend/src/app/legislators/[id]/page.tsx` — legislator detail page
- Next.js streaming with Suspense: https://nextjs.org/docs/app/building-your-application/routing/loading-ui-and-streaming
- React Suspense: https://react.dev/reference/react/Suspense
- Related: Issue #036 (misleading Recent Bills tab)
