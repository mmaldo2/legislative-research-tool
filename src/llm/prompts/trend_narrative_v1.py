"""Prompt for LLM-generated legislative trend narratives."""

PROMPT_VERSION = "trend-narrative-v1"

SYSTEM_PROMPT = """You are a legislative data analyst. Given aggregated \
legislative trend data, produce a clear narrative summary highlighting \
key trends, notable changes, and patterns. Be specific with numbers \
and percentages. Note any data limitations.

Respond with valid JSON matching this schema:
{
  "narrative": "2-3 paragraph narrative of the most significant trends",
  "key_findings": ["finding 1", "finding 2", ...],
  "confidence": 0.0-1.0
}"""

USER_PROMPT_TEMPLATE = """Analyze the following legislative trend data \
covering {period_covered}:

## Bill Volume by {group_by} ({bucket}ly)
{bills_data}

## Action Volume ({bucket}ly)
{actions_data}

## Topic Distribution ({bucket}ly)
{topics_data}

Total bills analyzed: {total_bills}

Produce a narrative summary with:
1. Key findings (3-5 bullet points)
2. A 2-3 paragraph narrative covering the most significant trends
3. A confidence assessment (0.0-1.0) based on data coverage"""
