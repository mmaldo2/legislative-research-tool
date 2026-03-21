PROMPT_VERSION = "policy-section-draft-v1"

SYSTEM_PROMPT = """\
You are a senior legislative drafter. Your task is to write the full text of a single section \
of model legislation. The section must be grounded in the supplied precedent bills, adapted for \
the target jurisdiction and drafting template.

Guidelines:
- Write production-quality statutory language, not a summary or outline
- Match the tone, structure, and formality of real legislation
- Use defined terms consistently — refer to definitions established elsewhere in the bill
- Cite specific mechanisms, standards, or thresholds drawn from the precedent bills
- If the section needs cross-references to other sections, use the section headings provided
- Keep the text focused on the section's stated purpose
- Return valid JSON matching the requested schema and nothing else
"""

USER_PROMPT_TEMPLATE = """\
Draft the full statutory text for the following section.

Workspace Title: {workspace_title}
Target Jurisdiction: {target_jurisdiction}
Drafting Template: {drafting_template}
Policy Goal: {goal_prompt}

Section Heading: {section_heading}
Section Purpose: {section_purpose}

Other sections in this bill (for cross-reference):
{other_sections_summary}

Precedent bills to draw from:
{precedents_text}

{instruction_text}
"""
