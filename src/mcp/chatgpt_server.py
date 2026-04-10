"""Standalone Streamable HTTP MCP server for ChatGPT Apps development.

Run locally with:
    python -m src.mcp.chatgpt_server

Default endpoint:
    http://0.0.0.0:8787/mcp
"""

from __future__ import annotations

import anyio

from src.mcp.http_app import build_chatgpt_mcp


def main() -> None:
    server = build_chatgpt_mcp()
    server.settings.host = "0.0.0.0"
    server.settings.port = 8787
    anyio.run(server.run_streamable_http_async)


if __name__ == "__main__":
    main()
