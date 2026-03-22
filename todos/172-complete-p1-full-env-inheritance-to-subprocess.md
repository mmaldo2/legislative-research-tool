---
status: pending
priority: p1
issue_id: 172
tags: [code-review, security]
dependencies: []
---

# Full Environment Inheritance Passes All Secrets to MCP Subprocess

## Problem Statement
`_inherit_env()` in `src/services/chat_service.py:378-384` returns `dict(os.environ)`, forwarding the entire process environment to the MCP subprocess. This includes all secrets: `WEBHOOK_ENCRYPTION_KEY`, cloud provider credentials, and any other sensitive variables — not just the ones the MCP server needs.

## Findings
- **Agent**: security-sentinel
- **Evidence**: `return dict(os.environ)` at line 383
- **Impact**: Violates principle of least privilege. If MCP server is compromised, attacker gets all env vars.

## Proposed Solutions
### Option A: Explicit allowlist (Recommended)
- **Effort**: Small (10 min)
- **Risk**: Low — may need to add vars if new tools need them
- Allowlist: `DATABASE_URL`, `PYTHONPATH`, `PATH`, `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `CONGRESS_API_KEY`, `GOVINFO_API_KEY`, `OPENSTATES_API_KEY`, plus Windows system vars (`SYSTEMROOT`, `TEMP`, `TMP`, `USERPROFILE`, `APPDATA`)

## Technical Details
- **File**: `src/services/chat_service.py:378-384`

## Acceptance Criteria
- [ ] Only required env vars passed to MCP subprocess
- [ ] MCP server starts and tools work with filtered env
- [ ] No cloud provider credentials or encryption keys leaked

## Work Log
- 2026-03-22: Created from code review
