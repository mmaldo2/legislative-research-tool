---
status: pending
priority: p3
issue_id: 150
tags: [quality, code-review]
---

# Dead Code — suggestionText State and ComposeError Class

## Problem Statement

Two pieces of dead code exist in the workspace feature: the `suggestionText` React state
variable is written but never read, and the `ComposeError` exception class is defined but
never raised. Dead code adds confusion and maintenance burden.

## Findings

- `suggestionText` state in the composer page is set via `setSuggestionText()` but the
  value is never consumed in JSX or passed to any component.
- `ComposeError` is defined in `policy_composer_service.py` but no code path raises it;
  generic exceptions or other error types are used instead.

## Technical Details

**Files:**
- `frontend/src/app/composer/[id]/page.tsx` — `suggestionText` / `setSuggestionText`
- `src/services/policy_composer_service.py` — `ComposeError` class definition

**Recommended fix:**
1. Remove the `suggestionText` state declaration and all `setSuggestionText` calls.
2. Remove the `ComposeError` class definition.
3. If `ComposeError` was intended for use, either wire it into the compose flow or
   remove it and file a separate issue to add proper error typing later.

## Acceptance Criteria

- [ ] `suggestionText` state and all references removed from the composer page.
- [ ] `ComposeError` class removed from `policy_composer_service.py`.
- [ ] No regressions — lint passes, tests pass, UI renders correctly.
