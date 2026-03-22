---
status: pending
priority: p2
issue_id: 146
tags: [architecture, code-review]
---

# Untyped Response Endpoints — Missing response_model Annotations

## Problem Statement

`list_workspace_conversations` and `get_precedent_insights` return raw dicts without
`response_model` annotations on their FastAPI route decorators. This means the OpenAPI
spec has no schema for these responses, breaking client code generation and making the
API contract implicit.

## Findings

- Both endpoints construct and return plain dictionaries.
- No Pydantic response model is defined for either response shape.
- All other workspace endpoints use `response_model` annotations.

## Technical Details

**Files:**
- `src/api/policy_workspaces.py` — route definitions for the two endpoints
- `src/schemas/policy_workspace.py` — location for new response schemas

**Recommended fix:**
1. Define `ConversationListResponse` and `PrecedentInsightsResponse` Pydantic models in
   the schema module.
2. Add `response_model=` to the corresponding route decorators.
3. Ensure the existing dict structures conform to the new schemas (fix any drift).

## Acceptance Criteria

- [ ] Both endpoints have `response_model` annotations.
- [ ] Pydantic response schemas are defined in `src/schemas/policy_workspace.py`.
- [ ] OpenAPI spec includes full schema definitions for both responses.
- [ ] Existing tests pass without response shape changes.
