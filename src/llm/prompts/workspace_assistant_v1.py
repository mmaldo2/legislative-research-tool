"""Workspace-aware research assistant prompt for policy composer."""

PROMPT_VERSION = "workspace-assistant-v1"

SYSTEM_PROMPT_TEMPLATE = """\
You are a legislative drafting research assistant embedded in a policy workspace. \
You help the user research, analyze, and refine their policy draft by providing \
grounded legislative research tied to the workspace context below.

## Current Workspace Context

{workspace_context}

## Available Tools

You have the same research tools as the general assistant:
- search_bills: Search for bills by keyword or semantic similarity. Filter by jurisdiction.
- get_bill_detail: Retrieve full bill record including text, sponsors, actions, and summary.
- list_jurisdictions: List all available jurisdictions.
- find_similar_bills: Find similar bills across jurisdictions for a given bill ID.
- analyze_version_diff: Compare two versions of the same bill.
- analyze_constitutional: Analyze a bill for constitutional concerns.
- analyze_patterns: Detect cross-jurisdictional patterns and model legislation.
- predict_bill_passage: Get ML-predicted probability of a bill clearing committee.
- search_govinfo: Search GovInfo for official federal documents.
- get_govinfo_document: Retrieve GovInfo document details.

## Drafting-Specific Guidelines

- Reference the workspace sections by heading when discussing the draft.
- When suggesting language improvements, format them as a quoted block so the user \
can easily identify actionable suggestions:
  > Suggested language: [your proposed text here]
- Ground your suggestions in the precedent bills listed in the workspace context. \
Cite specific bill identifiers when recommending approaches.
- Focus on the target jurisdiction's legal conventions and existing statutory framework.
- When asked about constitutional concerns, consider both the draft text and the \
precedent bills that informed it.
- Be specific about which section of the draft you're discussing.
- If the user asks you to research something, prioritize results from the target \
jurisdiction, then expand to other jurisdictions for comparison.
- Do not fabricate bill identifiers, provisions, or legislative history. Only report \
what the tools return.
"""

# Maximum characters of workspace context to include in system prompt
_MAX_CONTEXT_CHARS = 12000
_MAX_SECTION_DRAFT_CHARS = 2000
_MAX_PRECEDENT_SUMMARY_CHARS = 300


def format_workspace_context(
    *,
    title: str,
    target_jurisdiction: str,
    drafting_template: str,
    goal_prompt: str | None,
    precedent_summaries: list[dict],
    sections: list[dict],
) -> str:
    """Format workspace data into a context block for the system prompt.

    Args:
        title: Workspace title
        target_jurisdiction: Target jurisdiction ID
        drafting_template: Template type (e.g. general-model-act)
        goal_prompt: User's policy goal description
        precedent_summaries: List of dicts with keys: identifier, title, jurisdiction_id,
            status, ai_summary (optional)
        sections: List of dicts with keys: heading, status, content_markdown (optional)
    """
    parts: list[str] = []

    parts.append(f"**Title:** {title}")
    parts.append(f"**Target Jurisdiction:** {target_jurisdiction}")
    parts.append(f"**Drafting Template:** {drafting_template}")
    if goal_prompt:
        parts.append(f"**Policy Goal:** {goal_prompt}")

    # Precedent bills
    if precedent_summaries:
        parts.append("\n### Precedent Bills")
        for prec in precedent_summaries[:10]:
            ident = prec.get("identifier", "Unknown")
            jur = prec.get("jurisdiction_id", "")
            t = prec.get("title", "")
            line = f"- **{ident}** ({jur}): {t}"
            summary = prec.get("ai_summary")
            if summary:
                line += f"\n  Summary: {summary[:_MAX_PRECEDENT_SUMMARY_CHARS]}"
            parts.append(line)

    # Section outline with draft content
    if sections:
        parts.append("\n### Draft Sections")
        for idx, sec in enumerate(sections):
            status = sec.get("status", "outlined")
            heading = sec.get("heading", f"Section {idx + 1}")
            line = f"{idx + 1}. **{heading}** [{status}]"

            content = sec.get("content_markdown", "")
            if content:
                truncated = content[:_MAX_SECTION_DRAFT_CHARS]
                if len(content) > _MAX_SECTION_DRAFT_CHARS:
                    truncated += "... (truncated)"
                line += f"\n   Current draft:\n   {truncated}"

            parts.append(line)

    context = "\n".join(parts)
    return context[:_MAX_CONTEXT_CHARS]
