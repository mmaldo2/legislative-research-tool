import json
from unittest.mock import patch

import pytest

from src.schemas.compare import BillComparisonOutput


class _FakeBridge:
    def __init__(self, cwd):
        self.cwd = cwd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run_prompt(self, prompt: str, cwd=None, timeout: float = 60.0):
        payload = {
            "shared_provisions": ["Shared definition section"],
            "unique_to_a": ["Private right of action"],
            "unique_to_b": ["Agency rulemaking"],
            "key_differences": ["Different enforcement models"],
            "overall_assessment": "The bills address similar policy goals with different enforcement structures.",
            "similarity_score": 0.61,
            "is_model_legislation": False,
            "confidence": 0.78,
        }
        return [json.dumps(payload)], json.dumps(payload)


@pytest.mark.asyncio
async def test_generate_compare_via_codex_parses_output():
    from src.llm import codex_compare_adapter as module

    with patch.object(module, "CodexLocalBridge", _FakeBridge):
        output = await module.generate_compare_via_codex(
            bill_a_identifier="A1",
            bill_a_title="Bill A",
            bill_a_text="Text A",
            bill_b_identifier="B1",
            bill_b_title="Bill B",
            bill_b_text="Text B",
        )

    assert isinstance(output, BillComparisonOutput)
    assert output.similarity_score == 0.61
    assert output.unique_to_a == ["Private right of action"]
