---
status: pending
priority: p3
issue_id: "114"
tags: [code-review, testing, security]
dependencies: []
---

# Add Missing Test Coverage — LLM Fallback, Security Edge Cases

## Problem Statement

The test suite has good functional coverage (34 tests) but is missing security-relevant and edge case tests.

## Findings

- **Python Reviewer (LOW)**: No test for LLM error fallback path (confidence=0.0).
- **Security Sentinel (LOW)**: No test for unauthenticated access, no test for CSV with `+`, `-`, `@`, `|`, `;` prefixes, no test for `top_n` boundary values.
- **Pattern Recognition**: Missing empty data case for summary endpoint.

## Acceptance Criteria

- [ ] Test for LLM call failure returns fallback response with confidence=0.0
- [ ] Test for unauthenticated request returns 401/403
- [ ] Tests for all CSV dangerous prefix characters
- [ ] Test for `top_n=0` rejected by `ge=1` constraint
- [ ] Test for empty data in summary endpoint
