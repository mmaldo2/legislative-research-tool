---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, architecture]
dependencies: []
---

# Pydantic Schemas Defined Inline in Endpoint Files

## Problem Statement

Response and request schemas (`PersonResponse`, `SummarizeRequest`, `HealthResponse`, etc.) are defined inside endpoint files instead of in `src/schemas/`. This violates the project's own architectural convention documented in CLAUDE.md.

## Findings

- **kieran-python-reviewer (MEDIUM)**: Schemas should be in `src/schemas/`
- **architecture-strategist**: Convention violation
- **agent-native-reviewer**: Schema reuse blocked by location

**Affected files:**
- `src/api/people.py` — PersonResponse, PersonListResponse
- `src/api/analysis.py` — SummarizeRequest, ClassifyRequest
- `src/api/status.py` — HealthResponse, StatusResponse, IngestionRunResponse
- `src/api/search.py` — SearchResultItem, SearchResponse

## Proposed Solutions

### Option A: Move to src/schemas/ (Recommended)
- Create `src/schemas/api.py` or separate files per domain
- Import schemas in endpoint files
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] All Pydantic schemas live in `src/schemas/`
- [ ] Endpoint files only import schemas, not define them
