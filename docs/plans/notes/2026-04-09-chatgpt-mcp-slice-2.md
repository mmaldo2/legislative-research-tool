# ChatGPT MCP Slice 2

What landed
- Added investigation management tools to the ChatGPT MCP server:
  - `list_investigations`
  - `create_investigation`
  - `get_investigation`
  - `update_investigation`
  - `add_bill_to_investigation`
  - `remove_bill_from_investigation`
  - `update_investigation_notes`

Usage model
- These tools currently use an explicit `client_id` argument so ChatGPT can operate against the same investigation namespace the web app uses.
- This keeps the first workflow state model simple before introducing connector auth/user identity mapping.

Why this matters
- ChatGPT can now do more than search and inspect bills.
- It can maintain an investigation working set and notes over time.
- This is the first real step toward a ChatGPT-first research workflow rather than a read-only connector.

Next likely slice
- Add a delete investigation tool.
- Add memo/report artifact primitives that save outputs back into the app/workspace.
- Add lightweight identity/auth mapping so `client_id` does not have to be passed manually forever.
