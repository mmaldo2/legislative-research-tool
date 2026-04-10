# ChatGPT MCP Slice 4

What landed
- Added lightweight identity mapping for ChatGPT/connector workflows.
- Investigation and artifact tools can now use either:
  - `client_id`
  - or `connector_user_id`
- `connector_user_id` is converted into a stable internal client id (`chatgpt:<hash>`), so ChatGPT sessions can work against a durable investigation namespace without exposing the raw app client id.

New workflow primitive
- `save_investigation_snapshot`
  - Creates a markdown snapshot artifact from the current investigation state.
  - Useful for check-ins, summaries, and preserving the current working set.

New MCP resource
- `legislative://connector/workflow`
  - A lightweight connector workflow reference resource.

Why this matters
- The connector no longer has to pass raw web-app client ids around for most use cases.
- We now have a better bridge between conversational usage and durable app state.
- Snapshot artifacts make it easier to hand off work between ChatGPT, Hermes, and the standalone product.
