# ChatGPT Connector Dev Setup

Local MCP server
- Start with: `python -m src.mcp.chatgpt_server`
- Endpoint: `http://localhost:8787/mcp`

For ChatGPT developer mode
1. Expose the local MCP server with an HTTPS tunnel such as ngrok.
2. Use the public HTTPS URL ending in `/mcp` when creating the connector in ChatGPT developer mode.
3. Refresh the connector after changing tool metadata.

Current tool groups
- Research read tools
  - `search_bills`
  - `get_bill_detail`
  - `list_jurisdictions`
  - `find_similar_bills`
  - `search_govinfo`
  - `get_govinfo_document`
- Investigation tools
  - `list_investigations`
  - `create_investigation`
  - `get_investigation`
  - `update_investigation`
  - `add_bill_to_investigation`
  - `remove_bill_from_investigation`
  - `update_investigation_notes`
  - `delete_investigation`
- Artifact tools
  - `save_investigation_memo`
  - `save_investigation_snapshot`
  - `save_investigation_research_brief`
  - `list_investigation_artifacts`
  - `get_investigation_artifact`

Identity options
- Investigation/artifact tools accept either:
  - `client_id`
  - `connector_user_id`
- `connector_user_id` is hashed into a stable internal client id so ChatGPT-side workflows can preserve state without manually reusing the web app’s raw client id.
