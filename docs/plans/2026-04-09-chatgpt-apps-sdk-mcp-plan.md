# ChatGPT Apps SDK / MCP Migration Plan

Goal: shift the legislative research product toward a ChatGPT-first architecture by making the backend a clean MCP tool server for ChatGPT Apps, while de-emphasizing direct in-app provider-owned reasoning paths.

Why this direction
- The current app is strongest as a data + workflow engine: search, bill detail, similar bills, collections/investigations, and research primitives.
- The current direct LLM integration path is brittle and provider-coupled.
- The OpenAI Apps SDK quickstart points toward an officially supported model-hosted architecture: ChatGPT runs the model and our system exposes MCP tools and optional UI.

Target architecture
- Backend remains the system of record and tool/data plane.
- ChatGPT becomes the primary reasoning/runtime shell for conversational workflows.
- MCP tools expose the highest-value research actions.
- The standalone web app remains useful for browsing, investigation management, and evidence views, but direct built-in assistant/report generation becomes secondary over time.

Core product loop in the target state
1. User opens the legislative connector/app inside ChatGPT.
2. ChatGPT calls MCP tools against our backend.
3. User searches bills, inspects bill detail, finds analogs, and manages investigations from ChatGPT.
4. Optional UI components inside ChatGPT present richer investigation/search state.
5. The standalone app remains available as a companion workspace rather than the only shell.

---

## Phase 1: Establish a ChatGPT-connectable MCP surface

Objective
- Reuse existing backend research primitives through a Streamable HTTP MCP endpoint suitable for ChatGPT connector/app development.

Scope
- Add an HTTP MCP app/endpoint in addition to the existing stdio MCP server.
- Expose the safest highest-value tools first:
  - search_bills
n  - get_bill_detail
  - list_jurisdictions
  - find_similar_bills
  - search_govinfo
  - get_govinfo_document
- Keep LLM-powered tools out of the first slice unless explicitly configured.

Deliverables
- HTTP MCP app mounted at /mcp or runnable as a dedicated server.
- Local docs explaining how to connect it from ChatGPT developer mode.
- Basic health verification.

Success criteria
- ChatGPT Apps-compatible clients can discover and call the core read-oriented tools.
- No implicit Claude dependency in the connector flow.

---

## Phase 2: Add investigation management primitives to MCP

Objective
- Let ChatGPT work with the user’s investigation workflow, not just raw bills.

Add tools such as
- list_investigations
- get_investigation
- create_investigation
- add_bill_to_investigation
- remove_bill_from_investigation
- update_investigation_notes

Success criteria
- A user can create or continue an investigation from ChatGPT without dropping into the standalone UI for every operation.

---

## Phase 3: Optional ChatGPT UI components

Objective
- Add Apps SDK UI resources for richer stateful visualization inside ChatGPT.

Candidate components
- search results panel
- bill detail panel
- investigation workspace panel
- evidence list / memo artifact viewer

Success criteria
- ChatGPT interaction feels like a lightweight legislative workspace, not only a tool-call transcript.

---

## Phase 4: Decide what remains direct-provider in the standalone app

Objective
- Reduce duplicated model orchestration responsibility in the standalone app.

Likely direction
- Keep backend-owned data transformations and caching.
- Reduce direct embedded assistant/report routes unless they are truly needed outside ChatGPT.
- If retained, make them explicit provider integrations rather than implicit fallbacks.

---

## First-slice implementation plan

### Slice A: HTTP MCP endpoint for core research tools
Files likely
- `src/mcp/http_app.py` or equivalent
- `src/api/app.py`
- `src/mcp/server.py` (shared helpers if needed)
- `docs/plans/` or `docs/` setup note

Implementation goals
- Create a FastMCP-based HTTP app mounted at `/mcp`.
- Reuse existing backend tool handlers rather than re-implementing research logic.
- Expose only read-oriented tools in the first slice.
- Return structured JSON outputs where possible.

Verification
- The MCP HTTP app starts.
- Tool discovery works.
- Calling a few core tools returns valid structured results.

### Slice B: Documentation for local connector development
Implementation goals
- Add a short note describing:
  - local server URL
  - how to tunnel if needed
  - how to add the connector in ChatGPT developer mode
  - which tools are available in the first slice

---

## Risks / watchouts
- Apps SDK / MCP is not a drop-in replacement for the current LLM harness.
- ChatGPT-hosted workflows and standalone web app workflows should not diverge too far.
- Authentication and per-user investigation ownership will matter once connector use becomes real.
- First slice should stay read-heavy and low-risk.

## Recommended immediate next move
Implement Slice A now:
- add a Streamable HTTP MCP endpoint for the existing core research tools
- mount it under the current backend
- verify it locally
