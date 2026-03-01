---
status: complete
priority: p3
issue_id: "042"
tags: [code-review, quality]
dependencies: []
---

# 042 - Duplicated error UI pattern across 4 components

## Problem Statement

The same error display pattern (a `div` with `border-destructive` styling and "Failed to fetch X" text) is copy-pasted across 4 components. Each instance uses identical styling but with a different noun. This violates DRY and means any future styling or behavior change to the error UI must be applied in 4 places.

## Findings

- The duplicated error div pattern appears in:
  - `frontend/src/components/search-results.tsx`
  - `frontend/src/components/legislators-list.tsx`
  - `frontend/src/components/jurisdiction-grid.tsx`
  - `frontend/src/components/jurisdiction-detail.tsx`
- Each instance uses the same `border-destructive` styling with only the error message text varying (e.g., "Failed to fetch bills", "Failed to fetch legislators", etc.).

## Proposed Solutions

1. Extract a reusable `<ApiError message="..." />` component that encapsulates the error div styling and layout.
2. Replace all 4 inline error divs with the new component.
3. Place the component at `frontend/src/components/api-error.tsx` (or `frontend/src/components/ui/api-error.tsx` if following a ui/ convention).

Example:
```tsx
// api-error.tsx
export function ApiError({ message }: { message: string }) {
  return (
    <div className="border border-destructive rounded-lg p-4 text-destructive">
      {message}
    </div>
  );
}
```

## Technical Details

- This is a pure presentation refactor with no behavioral change.
- The component is intentionally simple: a styled container with a message prop.
- If retry functionality is added later, it can be extended with an optional `onRetry` callback prop.

## Acceptance Criteria

- [ ] New `<ApiError />` component created with a `message` prop
- [ ] All 4 components updated to use `<ApiError />` instead of inline error divs
- [ ] Styling is identical to the current inline implementation
- [ ] All pages render errors correctly after the refactor
- [ ] No duplicate error div patterns remain in the codebase

## Work Log

_No work performed yet._

## Resources

- `frontend/src/components/search-results.tsx`
- `frontend/src/components/legislators-list.tsx`
- `frontend/src/components/jurisdiction-grid.tsx`
- `frontend/src/components/jurisdiction-detail.tsx`
