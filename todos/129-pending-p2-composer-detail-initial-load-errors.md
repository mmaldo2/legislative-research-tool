---
status: complete
priority: p2
issue_id: "129"
tags: [code-review, composer, frontend, reliability, ux]
dependencies: []
---

# Composer Detail Page Misreports Initial Load Failures as Not Found

## Problem Statement

The composer detail page stores the real API error message when the initial fetch fails, but then immediately renders a generic "Workspace not found" state because `workspace` remains `null`. That collapses ownership errors, rate limits, backend failures, and offline/network problems into a false 404-like experience and makes the new composer surface harder to debug and trust.

## Findings

1. **`load()` records the real failure message** in `frontend/src/app/composer/[id]/page.tsx:115-118`.
2. **The component exits early whenever `workspace` is null**, before the error banner can render (`frontend/src/app/composer/[id]/page.tsx:269-275`).
3. **This reproduces a known project pattern** where detail pages accidentally mask non-404 failures as missing resources; see the earlier review artifact in `todos/archive/029-complete-p2-all-errors-treated-as-404-on-detail-pages.md`.

## Proposed Solutions

### Option A: Render the stored error state before the null-workspace branch (Recommended)
1. Keep the current `error` state from `load()`.
2. If `error` is present after loading, render `ApiErrorBanner` plus a neutral fallback shell instead of the "Workspace not found" copy.
3. Reserve the null-workspace branch for confirmed 404/not-found outcomes only.
- Effort: Small
- Risk: Low

### Option B: Track explicit load outcomes
1. Add a separate `loadState` such as `idle | loading | ready | not_found | error`.
2. Set `not_found` only on true 404s and `error` for all other failures.
3. Render each state intentionally.
- Effort: Medium
- Risk: Low

## Acceptance Criteria

- [ ] Initial 403/429/500/network failures on `/composer/[id]` no longer render "Workspace not found"
- [ ] The stored API error message is visible on the initial load failure path
- [ ] True not-found behavior remains available for genuine missing workspaces
- [ ] A browser or component test covers the initial-load error branch

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-03-20 | Created | Found during Phase 1/2 composer review |
