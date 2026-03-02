---
status: pending
priority: p2
issue_id: "109"
tags: [code-review, agent-native, api]
dependencies: ["108"]
---

# Return 422 for Invalid Parameters Instead of Silent Coercion

## Problem Statement

Invalid `bucket` or `group_by` values are silently replaced with defaults ("month"/"jurisdiction"). An agent or client with a typo (`?bucket=monh`) gets a 200 response with differently-grouped data and no indication the parameter was ignored.

## Findings

- **Agent-Native Reviewer (CRITICAL)**: Silent coercion is the antithesis of agent-native design. Agents need explicit failure signals.
- **Pattern Recognition (P2)**: Rest of codebase uses FastAPI validation to reject invalid input (422).

**Note:** If todo #108 is implemented (Literal types for params), FastAPI will automatically return 422 for invalid values, making this todo redundant. These are linked as dependencies.

**Affected file:** `src/api/trends.py` lines 71-74, 111-114, 149-150

## Proposed Solutions

### Option A: Use Literal types (Recommended — via #108)
When `bucket: Literal["month", "quarter", "year"]` is used, FastAPI automatically rejects invalid values with a 422 response including the valid options. No manual validation needed.
- Effort: Trivial (done by #108) | Risk: Low

### Option B: Manual HTTPException
Keep `str` types but raise `HTTPException(422, ...)` with valid values in the error detail.
- Effort: Small | Risk: Low

## Acceptance Criteria

- [ ] Invalid `bucket` values return 422 with valid options listed
- [ ] Invalid `group_by` values return 422 with valid options listed
- [ ] API error responses include structured JSON with valid_values list
