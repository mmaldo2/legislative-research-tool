---
status: complete
priority: p2
issue_id: "014"
tags: [code-review, architecture]
dependencies: []
---

# Missing API Endpoints for Existing Data

## Problem Statement

Several data types exist in the database but have no API endpoints: votes, jurisdictions, sessions, and AI analyses listing. This limits the API's usefulness and means agents/clients can't access data that was ingested.

## Findings

- **agent-native-reviewer (CRITICAL)**: Votes, jurisdictions, sessions not exposed
- **agent-native-reviewer (CRITICAL)**: No endpoint to list/get AI analyses
- **agent-native-reviewer**: No compare or ask endpoints

**Missing endpoints:**
- `GET /api/v1/bills/{id}/votes` — Vote data
- `GET /api/v1/jurisdictions` — Available jurisdictions
- `GET /api/v1/sessions` — Legislative sessions
- `GET /api/v1/analyses` — List AI analyses
- `GET /api/v1/analyses/{id}` — Get specific analysis

## Proposed Solutions

### Option A: Add endpoints incrementally (Recommended)
- Prioritize: analyses listing > jurisdictions > sessions > votes
- Follow existing endpoint patterns
- **Effort**: Medium
- **Risk**: Low

### Option B: Defer to Phase 2
- Document as planned endpoints in API docs
- **Effort**: Small (docs only)
- **Risk**: Low

## Acceptance Criteria

- [ ] AI analyses are accessible via API
- [ ] Available jurisdictions and sessions are queryable
- [ ] All ingested data types have read endpoints
