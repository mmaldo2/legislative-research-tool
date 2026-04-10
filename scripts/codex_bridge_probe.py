"""Probe the local Codex delegated-auth bridge.

Usage:
  python scripts/codex_bridge_probe.py

This script does not read or print raw tokens. It verifies that:
- local Codex app-server can be started
- the current account is authenticated via ChatGPT
- an ephemeral thread can be started
- a turn can be initiated
"""

from __future__ import annotations

import json
from pathlib import Path

from src.llm.codex_local_bridge import CodexLocalBridge


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    with CodexLocalBridge(repo_root) as bridge:
        account = bridge.get_account()
        thread = bridge.start_ephemeral_thread()
        turn = bridge.start_turn(thread.id, "Say hello in one short sentence.")
        print(
            json.dumps(
                {
                    "account": {
                        "auth_type": account.auth_type,
                        "email": account.email,
                        "plan_type": account.plan_type,
                        "requires_openai_auth": account.requires_openai_auth,
                    },
                    "thread": {
                        "id": thread.id,
                        "cwd": thread.cwd,
                        "model": thread.model,
                        "model_provider": thread.model_provider,
                    },
                    "turn": turn,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
