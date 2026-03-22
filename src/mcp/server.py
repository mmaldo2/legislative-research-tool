"""MCP server exposing legislative research tools via stdio transport.

Exposes all 10 research tools (search_bills, get_bill_detail, etc.) so that
MCP-capable clients — Claude Desktop, IDE extensions, and the Claude Agent SDK —
can call them against our PostgreSQL database.

Usage:
    python -m src.mcp.server          # stdio transport (default)
    legis-mcp                         # via installed entry point
"""

import json
import logging
import sys

import mcp.types as types
from mcp.server.lowlevel import Server

# Route ALL logging to stderr — stdout is the MCP JSON-RPC protocol channel.
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

server = Server("legis-research")


def _convert_schema(tool_def: dict) -> types.Tool:
    """Convert an Anthropic SDK tool definition to an MCP Tool.

    The only difference is the key name: Anthropic uses ``input_schema``,
    MCP uses ``inputSchema``.
    """
    return types.Tool(
        name=tool_def["name"],
        description=tool_def["description"],
        inputSchema=tool_def["input_schema"],
    )


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    from src.llm.tools import RESEARCH_TOOLS

    return [_convert_schema(t) for t in RESEARCH_TOOLS]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    from src.api.chat import execute_tool
    from src.api.deps import get_anthropic_client
    from src.database import async_session_factory
    from src.llm.harness import LLMHarness

    logger.info("Tool call: %s(%s)", name, json.dumps(arguments)[:200])

    try:
        async with async_session_factory() as db:
            client = get_anthropic_client()
            harness = LLMHarness(db_session=db, client=client)
            result = await execute_tool(name, arguments, db, harness)
        logger.info("Tool %s returned %d chars", name, len(result))
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        error_json = json.dumps({"error": f"Tool '{name}' failed: {e}"})
        return [types.TextContent(type="text", text=error_json)]


async def run_stdio():
    """Run the MCP server over stdio transport."""
    from mcp.server.stdio import stdio_server

    logger.info("Starting legis-research MCP server (stdio)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Entry point for the legis-mcp command."""
    import anyio

    anyio.run(run_stdio)


if __name__ == "__main__":
    main()
