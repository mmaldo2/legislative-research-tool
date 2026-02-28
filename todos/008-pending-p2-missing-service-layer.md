---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, architecture]
dependencies: []
---

# Missing Service Layer — Fat Controllers

## Problem Statement

API route handlers contain business logic (DB queries, filtering, pagination) directly. This makes endpoints hard to test, reuse, and maintain. The codebase would benefit from a service layer separating business logic from HTTP concerns.

## Findings

- **architecture-strategist (HIGH)**: Fat controllers anti-pattern
- **kieran-python-reviewer**: Business logic in endpoint files
- **code-simplicity-reviewer**: Logic duplication across endpoints

**Affected files:** `src/api/bills.py`, `src/api/people.py`, `src/api/search.py`, `src/api/analysis.py`, `src/api/status.py`

## Proposed Solutions

### Option A: Extract service modules (Recommended)
- Create `src/services/bill_service.py`, `src/services/person_service.py`, etc.
- Move query building, filtering, pagination into services
- Endpoints become thin wrappers: parse request → call service → return response
- **Effort**: Medium
- **Risk**: Low

### Option B: Defer to Phase 2+
- Accept fat controllers for MVP, refactor when adding complexity
- **Effort**: None now
- **Risk**: Technical debt accumulates

## Acceptance Criteria

- [ ] Route handlers contain only HTTP concerns (parse, validate, respond)
- [ ] Business logic lives in service modules
- [ ] Services are independently testable
