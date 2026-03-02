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
    {
        "name": "analyze_version_diff",
        "description": (
            "Analyze differences between two versions of the same bill. Identifies substantive "
            "changes, their significance (major/moderate/minor), and overall direction of change. "
            "Requires a bill with at least two text versions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The bill ID to compare versions for.",
                },
                "version_a_id": {
                    "type": "string",
                    "description": (
                        "ID of the earlier version text. Omit to use the oldest available version."
                    ),
                },
                "version_b_id": {
                    "type": "string",
                    "description": (
                        "ID of the later version text. Omit to use the latest available version."
                    ),
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "analyze_constitutional",
        "description": (
            "Analyze a bill for potential constitutional concerns including First Amendment, "
            "Due Process, Equal Protection, Commerce Clause, and federal preemption issues. "
            "Returns severity-rated concerns with relevant precedents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The bill ID to analyze for constitutional issues.",
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "analyze_patterns",
        "description": (
            "Detect cross-jurisdictional legislative patterns and model legislation. "
            "Compares a bill against similar bills from other states to identify shared "
            "frameworks, common provisions, and potential source organizations (ALEC, NCSL, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The source bill ID to analyze for patterns.",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of similar bills to compare against (default 5).",
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "search_govinfo",
        "description": (
            "Search the GovInfo API for federal government documents including bills, "
            "committee reports, hearings, and Federal Register notices. Returns document "
            "titles, collection types, dates, and download links. Use this for live queries "
            "against the official federal government publishing office database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search query — keywords or phrases related to the "
                        "federal document you are looking for."
                    ),
                },
                "collection": {
                    "type": "string",
                    "description": (
                        "GovInfo collection code to filter results. "
                        "Common values: BILLS (legislation), CRPT (committee reports), "
                        "CHRG (hearings), FR (Federal Register), PLAW (public laws), "
                        "STATUTE (statutes at large). Omit to search all."
                    ),
                },
                "congress": {
                    "type": "string",
                    "description": (
                        "Congress number to filter (e.g. '118' for 118th Congress). "
                        "Omit to search all congresses."
                    ),
                },
                "page_size": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of results to return (max 100).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_govinfo_document",
        "description": (
            "Retrieve detailed metadata and download links for a specific GovInfo "
            "document package. Use the package_id from search_govinfo results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "package_id": {
                    "type": "string",
                    "description": (
                        "The GovInfo package identifier "
                        "(e.g. 'BILLS-118hr1234ih', 'CRPT-118srpt25')."
                    ),
                },
            },
            "required": ["package_id"],
        },
    },
]
