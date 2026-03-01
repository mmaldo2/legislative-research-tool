---
status: complete
priority: p2
issue_id: "051"
tags: [code-review, architecture, quality]
dependencies: []
---

# execute_tool is a 225-line Monolith Duplicating Service Logic

## Problem Statement

The `execute_tool` function is a monolithic `if/elif` dispatcher that re-implements database queries already available in `bill_service.py` and other modules. Same pattern repeated in export brief and compare endpoints.

## Findings

1. `execute_tool` (lines 41-225) handles 4 tools in one function with independent query logic per branch
2. `get_bill_detail` branch duplicates `bill_service.get_bill_detail()` patterns
3. `search_bills` branch duplicates `src/api/search.py` logic
4. `_extract_bill_text()` in compare.py also appears in analysis.py and chat.py
5. Agents: Python Reviewer (#8, #13), Architecture Strategist (K, B, Q)

## Proposed Solutions

### Option A: Registry pattern + delegate to services (Recommended)
- Create `_TOOL_HANDLERS` dict mapping tool names to handler functions
- Each handler delegates to existing service layer
- **Effort**: Medium
- **Risk**: Low

## Technical Details

- **Files**: `src/api/chat.py`, `src/services/` (new tool handlers)

## Acceptance Criteria

- [ ] Each tool has its own handler function
- [ ] Tool handlers delegate to existing services where possible
- [ ] `_extract_bill_text` is a shared utility

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-28 | Created from PR #8 review | |

## Resources

- PR: #8
