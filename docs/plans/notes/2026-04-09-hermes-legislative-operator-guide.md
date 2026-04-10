# Hermes Legislative Operator Guide

Goal
- Let Hermes operate directly over the legislative MCP surface as a research operator, not just as a code-maintenance assistant.

Core idea
- The legislative backend is now a shared tool plane.
- ChatGPT connectors and Hermes can both use the same primitives:
  - search legislation
  - inspect bill detail
  - find similar bills
  - manage investigations
  - save memo/snapshot/research brief artifacts

Identity model
- Preferred for conversational/connector-style workflows: `connector_user_id`
- Legacy/manual option: `client_id`
- The MCP layer maps `connector_user_id` into a stable internal namespace so work can persist across sessions.

Recommended Hermes workflow
1. Resolve identity
- Use a stable `connector_user_id` for the user/workstream.

2. Open or create an investigation
- `list_investigations`
- `create_investigation`
- `get_investigation`

3. Build the working set
- `search_bills`
- `get_bill_detail`
- `find_similar_bills`
- `add_bill_to_investigation`
- `update_investigation_notes`

4. Save durable outputs
- `save_investigation_memo`
- `save_investigation_snapshot`
- `save_investigation_research_brief`
- `list_investigation_artifacts`
- `get_investigation_artifact`

Recommended identity convention
- Use a stable `connector_user_id` per person or workflow, e.g. `marcus-main` or `team-policy-ops`.
- Let the MCP layer map that to a durable internal namespace.

5. Continue later
- Re-open the investigation by identity + collection id
- Review artifacts to maintain continuity

Good Hermes use cases
- Daily watchlist or topic monitoring across bills
- Building a policy investigation from a user goal
- Capturing thesis/evidence notes over time
- Saving structured briefs before handoff to humans
- Running repeatable QA/smoke workflows against the product itself

Operational guideline
- Treat investigations as the durable unit of work.
- Treat artifacts as the durable memory of outputs.
- Prefer snapshots/briefs for handoff points.
