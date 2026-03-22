"""Prompts for analyzing user-drafted policy text."""

PROMPT_VERSION = "draft-analysis-v1"

CONSTITUTIONAL_SYSTEM_PROMPT = """\
You are a constitutional law analyst reviewing draft legislation. Analyze the \
provided draft text for potential constitutional concerns. Focus on substantive \
legal issues, not stylistic preferences.
"""

CONSTITUTIONAL_USER_TEMPLATE = """\
Analyze this draft section for constitutional concerns.

Section Heading: {section_heading}
Target Jurisdiction: {jurisdiction}
Policy Goal: {goal_prompt}

Draft Text:
{draft_text}

Provide your analysis as JSON with these fields:
- concerns: list of objects, each with "provision", "concern_type" (e.g. \
"First Amendment", "Due Process", "Equal Protection", "Commerce Clause", \
"Preemption"), "severity" ("high"/"moderate"/"low"), "description", and \
"recommendation"
- risk_level: overall risk ("high"/"moderate"/"low"/"minimal")
- summary: 2-3 sentence overall assessment
- confidence: float 0-1
"""

PATTERNS_SYSTEM_PROMPT = """\
You are a legislative policy analyst comparing draft legislation against \
existing precedent bills. Identify patterns, influences, and deviations from \
established legislative approaches.
"""

PATTERNS_USER_TEMPLATE = """\
Compare this draft section against the precedent legislation context.

Section Heading: {section_heading}
Target Jurisdiction: {jurisdiction}
Policy Goal: {goal_prompt}

Draft Text:
{draft_text}

Precedent Context:
{precedent_context}

Provide your analysis as JSON with these fields:
- pattern_type: "identical"/"adapted"/"inspired"/"novel" (how closely does \
the draft follow precedent patterns?)
- shared_provisions: list of strings describing provisions shared with precedents
- key_variations: list of strings describing where the draft diverges
- recommendations: list of strings suggesting improvements based on precedent
- summary: 2-3 sentence overall assessment
- confidence: float 0-1
"""
