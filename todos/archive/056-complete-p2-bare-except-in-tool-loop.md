---
status: complete
priority: p2
issue_id: "056"
tags: [code-review, quality, security]
dependencies: []
---

# Bare except Exception in Chat Tool Loop

## Problem Statement

The tool execution catch block in the agentic loop catches all `Exception` types, masking structural failures like database connection errors. The loop continues feeding the LLM error messages, potentially burning through all 10 rounds with a broken database.

## Findings

1. `except Exception:` at `src/api/chat.py` ~line 338 catches everything
2. Tool loop continues on structural failures, potentially burning 10 rounds
3. Security events (injection attempts, resource exhaustion) are silently absorbed
4. Agents: Python Reviewer (#2), Security Sentinel (M3)

## Proposed Solutions

### Option A: Narrow exception types (Recommended)
- Catch `(ValueError, LookupError, sqlalchemy.exc.NoResultFound, sqlalchemy.exc.IntegrityError)`
- Let truly unexpected errors (connection failures, system errors) bubble up
- **Effort**: Small
- **Risk**: Low

## Technical Details

- **Files**: `src/api/chat.py`

## Acceptance Criteria

- [ ] Tool loop catches only expected failure modes
- [ ] Database connection errors and system errors propagate to the global handler

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
