---
status: complete
priority: p3
issue_id: "061"
tags: [code-review, frontend, accessibility]
dependencies: []
---

# Frontend A11y + Validation: Aria-labels, parseInt Guard, useEffect Deps

## Problem Statement

Several accessibility and minor validation issues in the frontend: icon-only buttons lack accessible labels, `parseInt` not validated for NaN, `useEffect` dependency array incomplete, and inline style for chat height.

## Findings

1. Send button, delete buttons, and save-notes buttons have no `aria-label` or `sr-only` text — invisible to screen readers
2. `/collections/abc` → `parseInt` returns NaN, passed to API as `/collections/NaN`
3. `useEffect(() => { load(); }, [collectionId])` — `load` closes over `collectionId` but isn't in deps or useCallback'd
4. `style={{ height: "calc(100vh - 8rem)" }}` — hardcoded header height, should use Tailwind
5. Agent: TypeScript Reviewer (#4, #9, #11, #13)

## Proposed Solutions

### Option A: Fix all
- Add `<span className="sr-only">...</span>` to icon-only buttons
- Add NaN guard on parseInt with `notFound()` redirect
- Wrap `load` in `useCallback` or move inside useEffect
- Replace inline style with Tailwind class
- **Effort**: Small

## Technical Details

- **Files**: `frontend/src/app/assistant/page.tsx`, `frontend/src/app/collections/page.tsx`, `frontend/src/app/collections/[id]/page.tsx`

## Acceptance Criteria

- [ ] All icon-only buttons have accessible labels
- [ ] Invalid collection IDs show "not found" instead of NaN errors
- [ ] No React strict mode warnings about effect dependencies
- [ ] No inline styles

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
