---
status: pending
priority: p3
issue_id: "045"
tags: [code-review, architecture]
dependencies: []
---

# 045 - Manual type mirroring not sustainable

## Problem Statement

The frontend maintains 15 TypeScript interfaces that are manually written to match the backend's Pydantic schemas. As the API grows in Phase 3, these hand-maintained types will inevitably drift from the backend, causing silent type mismatches and runtime errors. One drift has already been identified: the backend types `ai_summary` as `dict | None` but the frontend assumes `BillSummaryOutput | null`.

## Findings

- 15 TypeScript interfaces in `frontend/src/types/api.ts` are manually maintained to mirror Pydantic schemas in `src/schemas/*.py`.
- There is no automated mechanism to detect or prevent drift between the two layers.
- Known existing drift: `ai_summary` is typed as `dict | None` on the backend (an unstructured dictionary) but as `BillSummaryOutput | null` on the frontend (a structured interface with specific fields). This means the frontend may access properties that do not exist on the actual API response.
- As Phase 3 adds more endpoints and response shapes, the maintenance burden and drift risk will increase linearly.

## Proposed Solutions

1. Use `openapi-typescript` to auto-generate TypeScript types from FastAPI's OpenAPI spec.
2. Add a generation script to the project:
   ```bash
   npx openapi-typescript http://localhost:8000/openapi.json -o frontend/src/types/api.generated.ts
   ```
3. Replace manual interfaces in `frontend/src/types/api.ts` with imports from the generated file.
4. Add the generation step to the CI pipeline or a pre-build script to catch drift early.

## Technical Details

- FastAPI automatically generates an OpenAPI 3.x spec at `/openapi.json`. This spec includes all Pydantic model definitions.
- `openapi-typescript` reads the OpenAPI spec and produces TypeScript interfaces that exactly match the API's response shapes, including nested objects, enums, and union types.
- The generated file should be committed to the repo (not gitignored) so that CI can diff it against the spec and fail if they are out of sync.
- For the `ai_summary` field specifically, the backend schema should be tightened from `dict | None` to a proper Pydantic model to ensure the generated TypeScript type is useful.

## Acceptance Criteria

- [ ] `openapi-typescript` added as a dev dependency
- [ ] Type generation script added to `package.json` (e.g., `"generate:types"`)
- [ ] Generated types file created at `frontend/src/types/api.generated.ts`
- [ ] Manual interfaces in `frontend/src/types/api.ts` replaced with imports from generated file
- [ ] `ai_summary` backend schema tightened from `dict | None` to a Pydantic model
- [ ] CI step or pre-build hook added to regenerate types and fail on drift
- [ ] All existing components compile against the generated types

## Work Log

_No work performed yet._

## Resources

- `frontend/src/types/api.ts`
- `src/schemas/*.py`
- [openapi-typescript](https://github.com/drwpow/openapi-typescript)
- [FastAPI OpenAPI Schema Generation](https://fastapi.tiangolo.com/tutorial/schema-extra-example/)
