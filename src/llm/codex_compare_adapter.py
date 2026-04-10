"""Codex-backed comparison helpers for delegated ChatGPT-auth reuse."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.llm.codex_local_bridge import CodexLocalBridge
from src.schemas.compare import BillComparisonOutput


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def generate_compare_via_codex(
    *,
    bill_a_identifier: str,
    bill_a_title: str,
    bill_a_text: str,
    bill_b_identifier: str,
    bill_b_title: str,
    bill_b_text: str,
) -> BillComparisonOutput:
    prompt = f"""
You are comparing two legislative bills for the app's compare feature.
Return ONLY valid JSON matching this shape:
{{
  "shared_provisions": [string],
  "unique_to_a": [string],
  "unique_to_b": [string],
  "key_differences": [string],
  "overall_assessment": string,
  "similarity_score": number,
  "is_model_legislation": boolean,
  "confidence": number
}}

Bill A:
Identifier: {bill_a_identifier}
Title: {bill_a_title}
Text:
{bill_a_text}

Bill B:
Identifier: {bill_b_identifier}
Title: {bill_b_title}
Text:
{bill_b_text}
""".strip()

    def _run() -> str:
        with CodexLocalBridge(_repo_root()) as bridge:
            _deltas, final_text = bridge.run_prompt(prompt, cwd=_repo_root(), timeout=120.0)
            return final_text

    final_text = await asyncio.to_thread(_run)
    data = json.loads(final_text)
    return BillComparisonOutput(**data)
