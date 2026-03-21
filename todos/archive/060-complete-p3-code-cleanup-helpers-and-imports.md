---
status: complete
priority: p3
issue_id: "060"
tags: [code-review, quality, cleanup]
dependencies: []
---

# Code Cleanup: Extract Helpers, Fix Imports, Use func.now()

## Problem Statement

Several minor code quality issues across the PR: duplicated text extraction, inline import, _generate_title edge case, server_default pattern, and unused imports.

## Findings

1. Text extraction pattern duplicated 3 times in chat agentic loop — extract `_extract_text()` helper (`src/api/chat.py`)
2. `_generate_title` returns empty string on empty input — add "Untitled conversation" fallback (`src/api/chat.py`)
3. `import anthropic` inline in function body — move to module level (`src/api/chat.py`)
4. `server_default="now()"` — use `func.now()` for explicit SQLAlchemy form (`src/models/collection.py`, `src/models/conversation.py`)
5. `CardDescription` imported but unused in similar-tab.tsx; unused variable `i` in comparison-view.tsx
6. Inline truncation in similar-tab.tsx — use existing `truncate()` from format.ts
7. Agents: Simplicity Reviewer (#1, #3), Python Reviewer (#11, #17, #22), TypeScript Reviewer (#12, #14, #15)

## Proposed Solutions

### Option A: Fix all (Recommended)
- Extract `_extract_text(response) -> str` helper in chat.py
- Add `if not text: return "Untitled conversation"` guard
- Move `import anthropic` to top of file
- Change `server_default="now()"` to `server_default=func.now()`
- Remove unused imports/vars, use truncate() util
- **Effort**: Small

## Technical Details

- **Files**: `src/api/chat.py`, `src/models/collection.py`, `src/models/conversation.py`, `frontend/src/app/bills/[id]/similar-tab.tsx`, `frontend/src/app/compare/comparison-view.tsx`

## Acceptance Criteria

- [ ] No duplicated text extraction logic
- [ ] Empty messages produce "Untitled conversation"
- [ ] No inline imports
- [ ] SQLAlchemy func.now() used for server_default
- [ ] No unused imports or variables

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
