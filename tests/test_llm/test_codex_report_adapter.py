import json
from unittest.mock import patch

import pytest

from src.schemas.analysis import ReportOutput


class _FakeBridge:
    def __init__(self, cwd):
        self.cwd = cwd

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def run_prompt(self, prompt: str, cwd=None, timeout: float = 60.0):
        payload = {
            "title": "Privacy Memo",
            "executive_summary": "Summary",
            "sections": [{"heading": "Overview", "content": "Body"}],
            "bills_analyzed": 2,
            "jurisdictions_covered": ["us-ca", "us-co"],
            "key_findings": ["Finding 1"],
            "trends": ["Trend 1"],
            "generated_at": "2026-04-10T00:00:00Z",
            "confidence": 0.72,
        }
        return [json.dumps(payload)], json.dumps(payload)


@pytest.mark.asyncio
async def test_generate_report_via_codex_parses_report_output():
    from src.llm import codex_report_adapter as module

    with patch.object(module, "CodexLocalBridge", _FakeBridge):
        report = await module.generate_report_via_codex(
            query="privacy",
            bills_text="Bill: A",
            bill_count=2,
            jurisdiction_count=2,
            source_label="test-source",
        )

    assert isinstance(report, ReportOutput)
    assert report.title == "Privacy Memo"
    assert report.bills_analyzed == 2
    assert report.sections[0].heading == "Overview"
