---
status: pending
priority: p2
issue_id: "108"
tags: [code-review, architecture, agent-native, api]
dependencies: []
---

# Restore response_model + Use Literal Types for Enum Params

## Problem Statement

Three trend endpoints use `response_model=None`, disabling OpenAPI schema generation. Clients and agents reading the spec see no documented response shape. Additionally, `bucket` and `group_by` are plain `str` Query parameters — valid values are not discoverable via the API schema.

## Findings

- **Architecture Strategist (VIOLATION)**: Only place in codebase using `response_model=None`.
- **Agent-Native Reviewer (WARNING)**: OpenAPI spec shows no response body for 3 endpoints.
- **Agent-Native Reviewer (WARNING)**: Valid enum values not discoverable via API.
- **Pattern Recognition (P2)**: Other endpoints use explicit `response_model`.

**Affected file:** `src/api/trends.py` lines 55, 59-60, 67, 95, 99-100, 107, 135, 145

## Proposed Solutions

### Option A: Restore response_model + Literal types (Recommended)
1. Use `response_model=TrendResponse` (or `TrendTopicResponse`) for the JSON path
2. Use `Literal["month", "quarter", "year"]` for `bucket` param
3. Use `Literal["jurisdiction", "topic", "status", "classification"]` for `group_by` param
4. Add `responses=` metadata for CSV content type in OpenAPI
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] All 3 data endpoints have explicit `response_model`
- [ ] `bucket` and `group_by` use `Literal` types
- [ ] OpenAPI spec documents both JSON and CSV response formats
- [ ] `format` parameter uses an enum with alias
