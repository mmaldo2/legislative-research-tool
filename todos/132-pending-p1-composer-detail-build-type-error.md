---
status: complete
priority: p1
issue_id: "132"
tags: [code-review, composer, frontend, build, typescript]
dependencies: []
---

# Composer Detail Page Fails Production Build Due to Over-Narrow State Inference

## Problem Statement

The composer detail page currently fails `next build`, which blocks production deployment and prevented browser validation from continuing on a clean host-only frontend server. The root cause is that `draftingTemplate` state is inferred as the single literal value from the default option, but later code assigns an arbitrary `string` from API data.

## Findings

1. **The detail page initializes `draftingTemplate` without a generic type argument** in `frontend/src/app/composer/[id]/page.tsx:67`.
2. **The load path later assigns `workspaceData.drafting_template`**, which is typed as `string`, in `frontend/src/app/composer/[id]/page.tsx:111`.
3. **`next build` fails in production mode** with `Argument of type 'string' is not assignable to parameter of type 'SetStateAction<\"general-model-act\">'`.

## Proposed Solutions

### Option A: Widen the state type explicitly (Recommended)
1. Change the state declaration to `useState<string>(COMPOSER_TEMPLATE_OPTIONS[0].value)`.
2. Keep the existing API typing and select wiring unchanged.
3. Re-run `npm --prefix frontend run build` and the browser pass.
- Effort: Small
- Risk: Low

### Option B: Narrow the API type to the composer template union
1. Define a shared union type for composer templates.
2. Use it in the frontend API types and component state.
3. Ensure the backend schema enforces the same template vocabulary.
- Effort: Medium
- Risk: Low

## Acceptance Criteria

- [ ] `next build` passes with the composer detail page included
- [ ] `draftingTemplate` state accepts loaded workspace values without TypeScript errors
- [ ] Browser validation can run against a clean host-only frontend build
- [ ] Composer template values are typed consistently across API and UI

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found while attempting browser validation on the composer pages |
