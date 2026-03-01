"""Tool definitions for the research assistant chat (Anthropic SDK tool_use format)."""

RESEARCH_TOOLS = [
    {
        "name": "search_bills",
        "description": (
            "Search for bills across all jurisdictions using keyword or semantic search. "
            "Returns bill IDs, identifiers, titles, jurisdictions, and relevance scores."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query — keywords, phrases, or a natural "
                        "language description of the policy topic."
                    ),
                },
                "jurisdiction": {
                    "type": "string",
                    "description": (
                        "Filter by jurisdiction ID (e.g. 'us', 'us-ca', "
                        "'us-ny'). Omit to search all."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["keyword", "semantic", "hybrid"],
                    "description": (
                        "Search mode. 'hybrid' (default) combines keyword "
                        "and semantic search for best results."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_bill_detail",
        "description": (
            "Get full details of a specific bill including text, sponsors, legislative actions "
            "timeline, vote history, and AI-generated summary. Use the bill ID returned by "
            "search_bills."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The internal bill ID to retrieve (from search results).",
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "list_jurisdictions",
        "description": (
            "List all available jurisdictions (states, territories, and federal) with their "
            "IDs and names. Use this to help users identify the correct jurisdiction filter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "find_similar_bills",
        "description": (
            "Find bills similar to a given bill across jurisdictions. Useful for tracking "
            "model legislation, identifying policy trends, or finding parallel bills in "
            "other states."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The bill ID to find similar bills for.",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of similar bills to return (default 5).",
                },
            },
            "required": ["bill_id"],
        },
    },
]
