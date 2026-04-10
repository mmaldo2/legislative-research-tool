# ChatGPT MCP First Slice

What landed
- Added a Streamable HTTP MCP app mounted at `/mcp`.
- Reused existing backend research primitives rather than rebuilding search/detail logic.
- Exposed the first read-oriented ChatGPT-ready tools:
  - `search_bills`
  - `get_bill_detail`
  - `list_jurisdictions`
  - `find_similar_bills`
  - `search_govinfo`
  - `get_govinfo_document`

Local development notes
- Start the standalone MCP server with: `python -m src.mcp.chatgpt_server`
- Or after reinstalling the package: `legis-chatgpt-mcp`
- Backend MCP URL: `http://localhost:8787/mcp`
- For ChatGPT connector development, expose this URL publicly with a tunnel and use the HTTPS `/mcp` URL in ChatGPT developer mode.
- The initial connector slice was read-oriented and low-risk.
- Slice 2 now adds investigation management primitives for ChatGPT-driven workflow continuity.

Why this slice
- It gives ChatGPT a supported MCP surface over the strongest existing research primitives.
- It avoids coupling the first connector iteration to the currently fragile in-app assistant/report routes.
