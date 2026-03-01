---
status: pending
priority: p3
issue_id: "081"
tags: [code-review, accessibility, typescript, frontend]
dependencies: ["074"]
---

# Missing Accessibility Attributes on Analysis Tabs

## Problem Statement

The 3 new analysis tab components lack `aria-busy`, `role="alert"` on error states, and `aria-live` regions for dynamic content updates.

## Findings

- **Source**: Kieran TypeScript Reviewer
- **Location**: `version-diff-tab.tsx`, `constitutional-tab.tsx`, `patterns-tab.tsx`

## Proposed Solutions

### Option A: Add ARIA attributes
- Add `aria-busy={loading}` to analysis containers
- Add `role="alert"` to error messages
- Add `aria-live="polite"` to results area
- **Effort**: Small (best done in useAnalysis hook from todo 074)

## Acceptance Criteria

- [ ] Loading states have `aria-busy`
- [ ] Error messages have `role="alert"`
- [ ] Results areas have `aria-live="polite"`

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
