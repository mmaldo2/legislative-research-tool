"""Codex-backed report generation helpers for delegated ChatGPT-auth reuse."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.llm.codex_local_bridge import CodexLocalBridge
from src.schemas.analysis import ReportOutput


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def generate_report_via_codex(
    *,
    query: str,
    bills_text: str,
    bill_count: int,
    jurisdiction_count: int,
    source_label: str,
) -> ReportOutput:
    prompt = f"""
You are generating a legislative research memo for the app's reports feature.
Return ONLY valid JSON matching this shape:
{{
  "title": string,
  "executive_summary": string,
  "sections": [{{"heading": string, "content": string}}],
  "bills_analyzed": integer,
  "jurisdictions_covered": [string],
  "key_findings": [string],
  "trends": [string],
  "generated_at": string,
  "confidence": number
}}

Query: {query}
Source label: {source_label}
Bills analyzed: {bill_count}
Jurisdictions covered: {jurisdiction_count}

Bills and evidence:
{bills_text}
""".strip()

    def _run() -> str:
        with CodexLocalBridge(_repo_root()) as bridge:
            _deltas, final_text = bridge.run_prompt(prompt, cwd=_repo_root(), timeout=120.0)
            return final_text

    final_text = await asyncio.to_thread(_run)
    data = json.loads(final_text)
    return ReportOutput(**data)
