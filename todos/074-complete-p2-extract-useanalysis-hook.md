---
status: complete
priority: p2
issue_id: "074"
tags: [code-review, refactor, typescript, duplication]
dependencies: []
---

# Extract useAnalysis<T> Hook from Triplicated Frontend State

## Problem Statement

All 3 new tab components (`version-diff-tab.tsx`, `constitutional-tab.tsx`, `patterns-tab.tsx`) duplicate identical state management logic: `useState` for result/loading/error, async handler with try/catch/finally, loading/error UI. This should be a shared custom hook.

## Findings

- **Source**: Kieran TypeScript Reviewer, Code Simplicity Reviewer
- **Location**: `frontend/src/app/bills/[id]/version-diff-tab.tsx`, `constitutional-tab.tsx`, `patterns-tab.tsx`
- **Evidence**: ~20 lines of identical state logic in each component

## Proposed Solutions

### Option A: Extract `useAnalysis<T>` hook
```typescript
function useAnalysis<T>(analyzeFn: () => Promise<T>) {
  const [result, setResult] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // ... handler with abort support
  return { result, loading, error, analyze };
}
```
- **Pros**: ~60 LOC saved, single place to add abort/cleanup (todo 075)
- **Effort**: Small
- **Risk**: None

## Recommended Action

Option A. Combine with todo 075 (abort/cleanup).

## Technical Details

- **Affected files**: New `frontend/src/hooks/use-analysis.ts`, 3 tab components
- **Related**: todo 075 (abort/cleanup on unmount)

## Acceptance Criteria

- [ ] Shared `useAnalysis<T>` hook created
- [ ] All 3 tab components use the shared hook
- [ ] Hook includes AbortController for cleanup

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-03-01 | Created from Phase 3 code review | |
