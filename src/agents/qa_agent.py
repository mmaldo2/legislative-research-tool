"""OpenAI Agents SDK QA agent scaffold for legislative app operations."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

DEFAULT_QA_MODEL = os.getenv("LEGIS_QA_AGENT_MODEL", "gpt-4o-mini")


class QAIssue(BaseModel):
    title: str = Field(..., description="Short title of the issue")
    category: str = Field(..., description="One of setup/runtime, backend bug, frontend bug, MCP issue, data-quality/product gap")
    severity: str = Field(..., description="critical, high, medium, or low")
    evidence: str = Field(..., description="Grounded evidence from the report")
    recommended_action: str = Field(..., description="Best next action")


class QAReportSummary(BaseModel):
    overall_status: str = Field(..., description="healthy, warning, or broken")
    healthy_count: int = 0
    warning_count: int = 0
    broken_count: int = 0
    top_issues: list[QAIssue] = Field(default_factory=list)
    summary: str = Field(..., description="Compact operator summary")


@function_tool
def parse_status_counts(report_markdown: str) -> str:
    """Parse a smoke or QA markdown report and count healthy/warning/broken markers."""
    lowered = report_markdown.lower()
    healthy = len(re.findall(r"\bhealthy\b", lowered))
    warning = len(re.findall(r"\bwarning\b", lowered))
    broken = len(re.findall(r"\bbroken\b", lowered))
    headings = re.findall(r"^#+\s+(.+)$", report_markdown, flags=re.MULTILINE)
    return json.dumps(
        {
            "healthy_count": healthy,
            "warning_count": warning,
            "broken_count": broken,
            "headings": headings[:20],
        }
    )


@function_tool
def extract_evidence_lines(report_markdown: str) -> str:
    """Extract notable lines from a QA report for grounded summarization."""
    lines = [line.strip() for line in report_markdown.splitlines() if line.strip()]
    evidence = [
        line
        for line in lines
        if any(token in line.lower() for token in ["error", "fail", "warning", "broken", "healthy", "503", "500", "200"])
    ]
    return json.dumps({"evidence_lines": evidence[:40]})


qa_agent = Agent(
    name="Legislative QA Agent",
    instructions=(
        "You summarize legislative app QA findings for operators. "
        "Use the provided tools to ground your summary in concrete report text. "
        "Return a concise structured QAReportSummary."
    ),
    model=DEFAULT_QA_MODEL,
    output_type=QAReportSummary,
    tools=[parse_status_counts, extract_evidence_lines],
)


async def summarize_report_text(report_markdown: str) -> QAReportSummary:
    result = await Runner.run(qa_agent, report_markdown)
    output = result.final_output
    if isinstance(output, QAReportSummary):
        return output
    if isinstance(output, dict):
        return QAReportSummary(**output)
    if isinstance(output, str):
        return QAReportSummary(
            overall_status="warning",
            summary=output,
            top_issues=[],
        )
    raise TypeError(f"Unexpected QA agent output type: {type(output)!r}")


async def summarize_report_file(path: str | Path) -> QAReportSummary:
    report_text = Path(path).read_text()
    return await summarize_report_text(report_text)
