# Automated QA Loop

This folder is used by autonomous QA/triage/fix jobs for the legislative research app.

Intended files
- `YYYY-MM-DD-smoke.md` — smoke-test report
- `YYYY-MM-DD-triage.md` — prioritized issue summary
- `YYYY-MM-DD-fix-pass.md` — conservative autonomous fix attempt summary

Loop design
1. Smoke test the live app and MCP server.
2. Save a grounded report.
3. Triage failures into setup, backend, UI, data-quality, and product gaps.
4. Optionally summarize a report with the OpenAI Agents SDK QA agent:
   - `python -m src.agents.cli qa-report docs/qa/YYYY-MM-DD-smoke.md`
   - or `legis-qa-agent qa-report docs/qa/YYYY-MM-DD-smoke.md`
5. Attempt one small safe fix when clearly scoped.
6. Re-run targeted verification.

Guardrails
- Prefer small, local, reversible fixes.
- Do not attempt major refactors autonomously.
- If the issue is ambiguous or high-risk, write it up instead of changing code.
