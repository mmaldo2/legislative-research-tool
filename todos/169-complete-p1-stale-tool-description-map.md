---
status: pending
priority: p1
issue_id: 169
tags: [code-review, quality, agent-native]
dependencies: []
---

# Stale _tool_description Map References Phantom Tools

## Problem Statement
The `_tool_description` dictionary in `src/services/chat_service.py:322-345` maps tool names to human-readable status messages for SSE `tool_status` events. It references 6 tools that don't exist (`get_bill_text`, `get_similar_bills`, `summarize_bill`, `search_precedent_language`, `get_trend_data`, `get_jurisdiction_info`, `get_legislator_info`) and is missing entries for 5 real tools (`list_jurisdictions`, `find_similar_bills`, `analyze_version_diff`, `analyze_patterns`, `predict_bill_passage`, `search_govinfo`, `get_govinfo_document`).

## Findings
- **Agent**: agent-native-reviewer
- **Evidence**: Compare `_tool_description` keys against `RESEARCH_TOOLS` names in `src/llm/tools.py`
- **Impact**: Frontend shows generic "Running tool_name..." for >50% of tools instead of descriptive status messages. Dead entries are maintenance noise.

## Proposed Solutions
### Option A: Replace with correct tool names (Recommended)
- **Effort**: Small (15 min)
- **Risk**: None
- Replace all entries with the 10 actual tool names from `RESEARCH_TOOLS`

## Technical Details
- **File**: `src/services/chat_service.py:322-345`
- **Reference**: `src/llm/tools.py` (canonical tool list)

## Acceptance Criteria
- [ ] All 10 tools in RESEARCH_TOOLS have matching entries in `_tool_description`
- [ ] No phantom tool names remain
- [ ] SSE tool_status events show descriptive messages for all tools

## Work Log
- 2026-03-22: Created from code review
