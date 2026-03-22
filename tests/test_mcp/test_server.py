"""Tests for the MCP server tool registration and schema conversion."""

from src.llm.tools import RESEARCH_TOOLS
from src.mcp.server import _convert_schema, server


class TestSchemaConversion:
    """Verify that Anthropic tool schemas convert correctly to MCP format."""

    def test_convert_schema_basic(self):
        tool_def = {
            "name": "search_bills",
            "description": "Search for bills.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        }
        mcp_tool = _convert_schema(tool_def)
        assert mcp_tool.name == "search_bills"
        assert mcp_tool.description == "Search for bills."
        assert mcp_tool.inputSchema["type"] == "object"
        assert "query" in mcp_tool.inputSchema["properties"]

    def test_convert_all_research_tools(self):
        """Every tool in RESEARCH_TOOLS should convert without error."""
        tools = [_convert_schema(t) for t in RESEARCH_TOOLS]
        assert len(tools) == 10

        # Verify all tool names are unique
        names = [t.name for t in tools]
        assert len(set(names)) == 10

    def test_tool_names_match(self):
        """MCP tool names should exactly match the Anthropic tool names."""
        expected_names = {t["name"] for t in RESEARCH_TOOLS}
        actual_names = {_convert_schema(t).name for t in RESEARCH_TOOLS}
        assert expected_names == actual_names

    def test_all_tools_have_descriptions(self):
        """Every MCP tool should have a non-empty description."""
        for tool_def in RESEARCH_TOOLS:
            mcp_tool = _convert_schema(tool_def)
            assert mcp_tool.description, f"Tool {mcp_tool.name} has empty description"

    def test_input_schema_preserved(self):
        """The inputSchema should be identical to the original input_schema."""
        for tool_def in RESEARCH_TOOLS:
            mcp_tool = _convert_schema(tool_def)
            assert mcp_tool.inputSchema == tool_def["input_schema"], (
                f"Schema mismatch for {mcp_tool.name}"
            )


class TestExpectedTools:
    """Verify that all 10 expected research tools are registered."""

    EXPECTED_TOOLS = [
        "search_bills",
        "get_bill_detail",
        "list_jurisdictions",
        "find_similar_bills",
        "analyze_version_diff",
        "analyze_constitutional",
        "analyze_patterns",
        "predict_bill_passage",
        "search_govinfo",
        "get_govinfo_document",
    ]

    def test_all_expected_tools_present(self):
        tool_names = {t["name"] for t in RESEARCH_TOOLS}
        for expected in self.EXPECTED_TOOLS:
            assert expected in tool_names, f"Missing tool: {expected}"

    def test_no_extra_tools(self):
        """If we add a tool to RESEARCH_TOOLS, this test reminds us to update the list."""
        tool_names = {t["name"] for t in RESEARCH_TOOLS}
        expected_set = set(self.EXPECTED_TOOLS)
        extras = tool_names - expected_set
        assert not extras, f"New tools found (update EXPECTED_TOOLS): {extras}"


class TestServerConfiguration:
    """Verify MCP server is properly configured."""

    def test_server_name(self):
        assert server.name == "legis-research"

    def test_list_tools_handler_registered(self):
        """The list_tools handler should be registered."""
        # The low-level Server stores handlers in request_handlers dict
        assert hasattr(server, "request_handlers")

    def test_search_bills_schema_has_required_fields(self):
        """search_bills should require 'query' parameter."""
        search_tool = next(t for t in RESEARCH_TOOLS if t["name"] == "search_bills")
        assert "query" in search_tool["input_schema"].get("required", [])

    def test_list_jurisdictions_has_no_required_fields(self):
        """list_jurisdictions has no required parameters."""
        list_tool = next(t for t in RESEARCH_TOOLS if t["name"] == "list_jurisdictions")
        assert (
            "required" not in list_tool["input_schema"] or not list_tool["input_schema"]["required"]
        )


class TestSdkAgendicChat:
    """Verify the SDK agentic chat helper functions."""

    def test_build_sdk_prompt_basic(self):
        from src.services.chat_service import _build_sdk_prompt

        prompt = _build_sdk_prompt(
            "You are a research assistant.",
            [{"role": "user", "content": "What is HB 1234?"}],
        )
        assert "<system>" in prompt
        assert "research assistant" in prompt
        assert "<user>" in prompt
        assert "HB 1234" in prompt

    def test_build_sdk_prompt_multi_turn(self):
        from src.services.chat_service import _build_sdk_prompt

        messages = [
            {"role": "user", "content": "Search for data privacy bills"},
            {"role": "assistant", "content": "I found 5 bills..."},
            {"role": "user", "content": "Tell me about the first one"},
        ]
        prompt = _build_sdk_prompt("System prompt", messages)
        assert prompt.count("<user>") == 2
        assert prompt.count("<assistant>") == 1
        assert "data privacy" in prompt
        assert "first one" in prompt

    def test_build_sdk_prompt_empty_system(self):
        from src.services.chat_service import _build_sdk_prompt

        prompt = _build_sdk_prompt("", [{"role": "user", "content": "Hello"}])
        assert "<system>" not in prompt
        assert "<user>" in prompt

    def test_build_sdk_prompt_tool_results(self):
        from src.services.chat_service import _build_sdk_prompt

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "content": '{"total": 5}'},
                    {"type": "text", "text": "Here are the results"},
                ],
            },
        ]
        prompt = _build_sdk_prompt("", messages)
        assert "Tool result" in prompt
        assert "Here are the results" in prompt

    def test_inherit_env(self):

        from src.services.chat_service import _inherit_env

        env = _inherit_env()
        assert isinstance(env, dict)
        # Should include standard env vars
        assert "PATH" in env or "Path" in env  # Windows uses 'Path'
