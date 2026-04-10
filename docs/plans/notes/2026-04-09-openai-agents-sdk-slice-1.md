# OpenAI Agents SDK Slice 1

What landed
- Added an OpenAI Agents SDK runtime scaffold under `src/agents/`.
- Implemented the first narrow agent: a QA Agent for summarizing smoke/QA reports.
- Added a CLI entrypoint for running the QA agent against a markdown report.

Files
- `src/agents/__init__.py`
- `src/agents/qa_agent.py`
- `src/agents/cli.py`
- `docs/plans/2026-04-09-openai-agents-sdk-plan.md`

CLI usage
- `python -m src.agents.cli qa-report docs/qa/YYYY-MM-DD-smoke.md`
- after reinstall/update: `legis-qa-agent qa-report docs/qa/YYYY-MM-DD-smoke.md`

Requirements
- `OPENAI_API_KEY` must be set to run the agent.

Why this slice
- Establishes the OpenAI Agents SDK runtime pattern cleanly.
- Avoids prematurely wiring the SDK into every existing app route.
- Creates a practical bridge into the daily QA loop and future operator workflows.
