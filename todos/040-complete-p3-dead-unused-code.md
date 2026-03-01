---
status: complete
priority: p3
issue_id: "040"
tags: [code-review, quality]
dependencies: []
---

# 040 - Dead code: unused types and API functions

## Problem Statement

Approximately 86 lines of unused type definitions and 3 unused exported functions exist across the frontend API layer. Dead code increases cognitive load during onboarding and maintenance, and can mislead developers into thinking these types and functions are actively consumed.

## Findings

- **Unused type definitions** (~86 lines): `VoteRecordResponse`, `VoteEventResponse`, `VoteEventListResponse`, `TopicClassificationOutput`, `AnalysisResponse`, `AnalysisListResponse`, `IngestionRunResponse`, `StatusResponse` are all defined but never referenced by any component or page.
- **Unused exported functions** (3): `listVoteEvents`, `getHealth`, `getStatus` are exported from the API client but have no call sites in the codebase.
- **Unused re-export**: `export { ApiError }` is never imported externally by any other module.
- Files affected:
  - `frontend/src/types/api.ts:144-229`
  - `frontend/src/lib/api.ts:125-143`

## Proposed Solutions

1. Remove all unused type definitions from `frontend/src/types/api.ts`.
2. Remove unused exported functions (`listVoteEvents`, `getHealth`, `getStatus`) from `frontend/src/lib/api.ts`.
3. Remove the dead `export { ApiError }` if no external consumer exists.
4. Add types and functions back individually when pages or features actually require them.

## Technical Details

- These types and functions were likely scaffolded in anticipation of future pages (vote tracking, health checks, ingestion monitoring) that have not yet been built.
- Removing them has zero runtime impact since they are never invoked or instantiated.
- If vote-tracking or health-check pages are added later, the types can be reintroduced (or auto-generated per issue 045).

## Acceptance Criteria

- [ ] All 8 unused type definitions are removed from `frontend/src/types/api.ts`
- [ ] All 3 unused exported functions are removed from `frontend/src/lib/api.ts`
- [ ] Dead `export { ApiError }` line is removed if confirmed unused
- [ ] `npm run build` and `npm run lint` pass with no errors
- [ ] No remaining references to removed symbols across the codebase

## Work Log

_No work performed yet._

## Resources

- `frontend/src/types/api.ts`
- `frontend/src/lib/api.ts`
