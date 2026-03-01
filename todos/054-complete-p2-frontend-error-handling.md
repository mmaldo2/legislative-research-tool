---
status: complete
priority: p2
issue_id: "054"
tags: [code-review, frontend, quality]
dependencies: []
---

# Frontend: Silent Error Swallowing + Missing Mutation Error Handling + window.prompt

## Problem Statement

Multiple `catch {}` blocks silently swallow errors with no user feedback. Two mutation handlers (handleRemove, handleSaveNotes) have no error handling at all. The save-to-collection "New collection" flow uses `window.prompt()` instead of a proper dialog.

## Findings

1. Silent `catch {}` in collections/page.tsx (load, handleDelete), save-to-collection.tsx (useEffect, handleCreateAndAdd)
2. `handleRemove` and `handleSaveNotes` in collections/[id]/page.tsx have zero try/catch — unhandled promise rejection
3. `window.prompt("Collection name:")` — blocking browser dialog, out of place in shadcn/ui app
4. Agents: TypeScript Reviewer (#3, #5, #6), Simplicity Reviewer (#7), Agent-Native Reviewer (#6)

## Proposed Solutions

### Option A: Add error states + use Dialog (Recommended)
- Add `console.error(e)` to all catch blocks at minimum
- Add try/catch to handleRemove and handleSaveNotes
- Replace `window.prompt()` with shadcn Dialog + Input component
- **Effort**: Small-Medium
- **Risk**: Low

## Technical Details

- **Files**: `frontend/src/app/collections/page.tsx`, `frontend/src/app/collections/[id]/page.tsx`, `frontend/src/components/save-to-collection.tsx`

## Acceptance Criteria

- [ ] All catch blocks at minimum log to console.error
- [ ] All mutation handlers have try/catch with user-facing error feedback
- [ ] Collection creation uses Dialog component instead of window.prompt

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
