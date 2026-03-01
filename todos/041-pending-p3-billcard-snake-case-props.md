---
status: pending
priority: p3
issue_id: "041"
tags: [code-review, quality, typescript]
dependencies: []
---

# 041 - BillCard props use snake_case instead of camelCase

## Problem Statement

The `BillCard` component interface uses `jurisdiction_id` (snake_case) as a prop name, which bleeds the API's naming convention into the React component layer. React and TypeScript conventions strongly favor camelCase for component props.

## Findings

- The `BillCard` interface at `frontend/src/components/bill-card.tsx:10` defines `jurisdiction_id` using snake_case.
- This naming originates from the API response shape and was passed through without remapping.
- Mixing naming conventions across layers creates inconsistency and makes it harder to distinguish between raw API data and component-level props.

## Proposed Solutions

1. Rename the prop from `jurisdiction_id` to `jurisdictionId` in the `BillCard` interface.
2. Update all call sites that pass this prop to map from the API response: `result.jurisdiction_id` to `jurisdictionId`.
3. Ensure any destructuring or usage within the `BillCard` component body is updated accordingly.

## Technical Details

- This is a straightforward rename with no behavioral change.
- The mapping from snake_case API response to camelCase props should happen at the call site (or in a data-mapping utility), not inside the component.
- Example transformation at call site:
  ```tsx
  <BillCard jurisdictionId={result.jurisdiction_id} ... />
  ```

## Acceptance Criteria

- [ ] `jurisdiction_id` prop renamed to `jurisdictionId` in the `BillCard` interface
- [ ] All call sites updated to map `result.jurisdiction_id` to `jurisdictionId`
- [ ] Component internals updated to use `jurisdictionId`
- [ ] TypeScript compilation passes with no errors
- [ ] No remaining snake_case props in `BillCard` interface

## Work Log

_No work performed yet._

## Resources

- `frontend/src/components/bill-card.tsx`
