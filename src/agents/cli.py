"""CLI entrypoints for OpenAI Agents SDK workflows."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from src.agents.qa_agent import summarize_report_file


def _require_openai_key() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is required to run the OpenAI Agents SDK workflows."
        )


async def _run_qa_report(path: str) -> int:
    _require_openai_key()
    summary = await summarize_report_file(path)
    print(json.dumps(summary.model_dump(), indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Legislative OpenAI Agents SDK utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    qa_parser = subparsers.add_parser("qa-report", help="Summarize a QA markdown report")
    qa_parser.add_argument("path", help="Path to the markdown report")

    args = parser.parse_args()

    try:
        if args.command == "qa-report":
            exit_code = asyncio.run(_run_qa_report(args.path))
        else:
            parser.error(f"Unknown command: {args.command}")
            return
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    raise SystemExit(exit_code)
