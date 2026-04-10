# OpenAI Agents SDK Integration Plan

Goal: introduce an OpenAI Agents SDK runtime for application-owned agents while reusing the legislative MCP and backend tool/data plane already built.

Why this direction
- The OpenAI Agents SDK is a better architectural match than a plain provider swap because it supports application-owned orchestration, tools, state, and handoffs.
- The repo now has a useful MCP/data plane and ChatGPT-facing MCP server.
- We can use the Agents SDK as the runtime brain and the legislative MCP surface as the operational substrate.

Target architecture
- OpenAI Agents SDK runtime modules live in `src/agents/`.
- The backend remains the source of truth for legislative data and investigation state.
- The legislative MCP tool plane remains available for ChatGPT and Hermes/operator workflows.
- The first agents should be narrow and operationally useful rather than trying to replace every existing assistant/report route at once.

Recommended sequence

## Phase 1: QA Agent runtime
Objective
- Create a small, application-owned QA agent runtime that can help exercise and summarize product state using narrow tools.

Scope
- Add an OpenAI Agents SDK-based module under `src/agents/`.
- Implement a first QA-oriented agent that can:
  - summarize app health inputs
  - turn smoke-test findings into a structured QA brief
  - optionally call small local function tools for formatting/categorization
- Keep this first slice independent from the current web app assistant route.

Success criteria
- A CLI entrypoint can run the QA agent with a supplied prompt/input.
- The QA agent returns a structured, useful summary.
- The code establishes a clean pattern for future research agents.

## Phase 2: Legislative Research Agent
Objective
- Add a research/investigation-focused agent runtime.

Scope
- Add function tools or MCP-backed tools for:
  - search bills
  - get bill detail
  - find similar bills
  - manage investigations and artifacts
- Use the Agents SDK runtime to orchestrate multi-step research workflows.

## Phase 3: Handoffs / specialist agents
Objective
- Split the work into specialized agents.

Candidate specialists
- Search/Triage Agent
- Bill Detail Analyst
- Investigation Manager
- QA/Triage Agent
- Memo/Brief Composer

## Phase 4: Production integration decisions
Objective
- Decide whether to replace or de-emphasize current direct in-app assistant/report routes with Agents SDK-backed workflows.

---

## First implementation slice to build now

Slice: QA Agent runtime scaffold

Files to add
- `src/agents/__init__.py`
- `src/agents/qa_agent.py`
- `src/agents/cli.py`

Behavior
- Use the OpenAI Agents SDK Python package (`from agents import Agent, Runner, function_tool`).
- Define a small QA agent with one or two local function tools for categorizing findings.
- Accept a markdown/text report input and return a compact structured QA summary.
- Provide a CLI runner so we can invoke it directly from cron/manual flows.

Verification
- Local CLI invocation succeeds when OpenAI credentials are available.
- The module imports cleanly even before wiring it into the larger app.
- The design is extensible toward future legislative research agents.

Notes
- This first slice should not try to solve connector auth, in-app route migration, or full MCP tool integration.
- It should establish the OpenAI Agents SDK runtime pattern cleanly and safely.
