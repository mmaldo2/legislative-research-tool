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
            "timeline, and AI-generated summary. For roll-call vote tallies and how members "
            "voted, use get_vote_event. Use the bill ID returned by search_bills."
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
        "name": "get_vote_event",
        "description": (
            "Get a single roll-call vote event by its vote_event_id: the official tallies "
            "(yes/no/other counts, result, motion, chamber, date) plus every member's recorded "
            "vote with their party AS OF the vote date (point-in-time, so party-switchers are "
            "attributed correctly). Use this to answer questions about how members voted on a "
            "specific roll call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vote_event_id": {
                    "type": "string",
                    "description": "The roll-call vote event id.",
                },
            },
            "required": ["vote_event_id"],
        },
    },
    {
        "name": "get_bill_votes",
        "description": (
            "List the roll-call vote events for a bill by its bill_id: one row per roll call with "
            "its vote_event_id, chamber, vote_date, motion text, and result. Use this to find "
            "which roll call(s) a bill received and to get the vote_event_id you can cite or pass "
            "to get_vote_event. An empty list means the bill received no roll-call votes; an error "
            "means no such bill exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The internal bill ID.",
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "get_bill_cosponsors",
        "description": (
            "List the cosponsors of a bill by its bill_id: one row per cosponsor with their "
            "person_id and name. Cosponsors are the members who signed on to support the bill — "
            "NOT the primary sponsor (the author). An empty list means the bill has no cosponsors; "
            "an error means no such bill exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The internal bill ID.",
                },
            },
            "required": ["bill_id"],
        },
    },
    {
        "name": "get_member_sponsorships",
        "description": (
            "List the bills a member PRIMARY-sponsored (authored) in a given congress, by their "
            "person_id: one row per bill with its bill_id. These are the bills the member led -- "
            "NOT cosponsored, and NOT pre-filtered by whether they received a vote. To find which "
            "got a roll-call vote, call get_bill_votes on each bill_id. An empty list means the "
            "member primary-sponsored no bills in that congress; an error means no such person "
            "exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {
                    "type": "string",
                    "description": "The internal person ID.",
                },
                "congress": {
                    "type": "string",
                    "description": "The congress number, e.g. '110'.",
                },
            },
            "required": ["person_id", "congress"],
        },
    },
    {
        "name": "list_vote_events",
        "description": (
            "List every roll-call vote event in a (congress, chamber) window with its official "
            "tally: one row per roll call with its vote_event_id, yes_count, and no_count. Use "
            "this for questions that span all the roll-call votes of a whole Congress. Roll calls "
            "official tally is unavailable are omitted."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "congress": {
                    "type": "string",
                    "description": "The Congress number (e.g. '115').",
                },
                "chamber": {
                    "type": "string",
                    "description": "The chamber: 'house' or 'senate'.",
                },
            },
            "required": ["congress", "chamber"],
        },
    },
    {
        "name": "find_people",
        "description": (
            "Find legislators by name within a (congress, chamber) window: returns each matching "
            "member's person_id and name. Use this to resolve a member's name to the person_id "
            "that get_member_voting_record needs. An empty list means no member with that name "
            "voted in that window; more than one result means the name is shared by multiple "
            "members."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The member's full name."},
                "congress": {
                    "type": "string",
                    "description": "The Congress number (e.g. '115').",
                },
                "chamber": {
                    "type": "string",
                    "description": "The chamber: 'house' or 'senate'.",
                },
            },
            "required": ["name", "congress", "chamber"],
        },
    },
    {
        "name": "get_member_voting_record",
        "description": (
            "Get one member's recorded option on each roll call they voted on in a (congress, "
            "chamber) window: one row per record, each with its vote_event_id and the member's "
            "option (yea / nay / present / not_voting). Members do not vote on every roll call, "
            "so count the records returned. Use the person_id from find_people. An error means no "
            "such member voted in that window."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "person_id": {
                    "type": "string",
                    "description": "The member's person id (from find_people).",
                },
                "congress": {
                    "type": "string",
                    "description": "The Congress number (e.g. '115').",
                },
                "chamber": {
                    "type": "string",
                    "description": "The chamber: 'house' or 'senate'.",
                },
            },
            "required": ["person_id", "congress", "chamber"],
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
        "name": "predict_bill_passage",
        "description": (
            "Get the ML-predicted probability that a bill will clear committee, based on "
            "its current legislative activity (actions, sponsors, session timing). Returns "
            "a calibrated probability score, the top contributing features with their impact "
            "direction, the model version, and the historical base rate for comparison. "
            "Use this when users ask about a bill's chances of passing, want a quantitative "
            "assessment, or ask for a prediction."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "bill_id": {
                    "type": "string",
                    "description": "The bill ID to predict passage for.",
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
