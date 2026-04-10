"""Minimal local Codex app-server bridge for delegated ChatGPT-auth reuse.

This is an experimental proof-of-concept integration surface.
It talks to the locally authenticated Windows Codex runtime over stdio JSON-RPC,
so the legislative app can assess delegated-reuse feasibility without owning
OpenAI OAuth or handling raw tokens directly.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CodexBridgeError(RuntimeError):
    """Raised when the local Codex bridge cannot complete a request."""


@dataclass
class CodexAccount:
    auth_type: str
    email: str | None = None
    plan_type: str | None = None
    requires_openai_auth: bool = False


@dataclass
class CodexThread:
    id: str
    cwd: str | None = None
    model: str | None = None
    model_provider: str | None = None


class CodexLocalBridge:
    """Tiny JSON-RPC client for `codex app-server --listen stdio://`.

    This intentionally keeps the integration narrow:
    - initialize the app-server connection
    - read account/auth state
    - start an ephemeral thread
    - start a turn

    It is suitable for local delegated-auth feasibility tests, not production use.
    """

    def __init__(self, cwd: str | Path):
        self.cwd = self._to_windows_path(str(cwd))
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1

    def __enter__(self) -> "CodexLocalBridge":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            ["cmd.exe", "/c", "codex", "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.initialize()

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            self._proc.kill()
        finally:
            self._proc = None

    def initialize(self) -> dict[str, Any]:
        return self._request(
            "initialize",
            {
                "clientInfo": {"name": "legis-codex-bridge", "version": "0.1"},
                "capabilities": {"experimentalApi": True},
            },
        )

    def get_account(self) -> CodexAccount:
        result = self._request("account/read", {})
        account = result.get("account") or {}
        return CodexAccount(
            auth_type=account.get("type", "unknown"),
            email=account.get("email"),
            plan_type=account.get("planType"),
            requires_openai_auth=bool(result.get("requiresOpenaiAuth", False)),
        )

    @staticmethod
    def _thread_from_response(result: dict[str, Any]) -> CodexThread:
        thread = result.get("thread", {})
        return CodexThread(
            id=thread["id"],
            cwd=thread.get("cwd"),
            model=result.get("model"),
            model_provider=result.get("modelProvider"),
        )

    @staticmethod
    def _collect_turn_output(events: list[dict[str, Any]]) -> tuple[list[str], str]:
        deltas: list[str] = []
        final_text = ""
        for event in events:
            method = event.get("method")
            params = event.get("params", {})
            if method == "item/agentMessage/delta":
                delta = params.get("delta", "")
                if delta:
                    deltas.append(delta)
                    final_text += delta
            elif method == "item/completed":
                item = params.get("item", {})
                if item.get("type") == "agentMessage" and item.get("text"):
                    final_text = item["text"]
        return deltas, final_text

    def start_ephemeral_thread(self, cwd: str | Path | None = None) -> CodexThread:
        result = self._request(
            "thread/start",
            {
                "ephemeral": True,
                "approvalPolicy": "never",
                "cwd": self._to_windows_path(str(cwd or self.cwd)),
            },
        )
        return self._thread_from_response(result)

    def start_turn(self, thread_id: str, prompt: str) -> dict[str, Any]:
        return self._request(
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
            },
        )

    def run_prompt(self, prompt: str, cwd: str | Path | None = None, timeout: float = 60.0) -> tuple[list[str], str]:
        thread = self.start_ephemeral_thread(cwd=cwd)
        self.start_turn(thread.id, prompt)
        events = self._collect_until_thread_idle(thread.id, timeout=timeout)
        return self._collect_turn_output(events)

    def iter_events(self) -> Iterator[dict[str, Any]]:
        if self._proc is None or self._proc.stdout is None:
            raise CodexBridgeError("Codex app-server is not running")
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

    @staticmethod
    def _to_windows_path(path: str) -> str:
        if not path.startswith("/mnt/"):
            return path
        try:
            output = subprocess.check_output(["wslpath", "-w", path], text=True).strip()
            return output or path
        except Exception:
            return path

    def _read_message(self) -> dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise CodexBridgeError("Codex app-server is not running")
        line = self._proc.stdout.readline()
        if not line:
            raise CodexBridgeError("Codex app-server closed the connection")
        line = line.strip()
        if not line:
            return self._read_message()
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise CodexBridgeError(f"Invalid JSON from Codex app-server: {line}") from exc

    def _collect_until_thread_idle(self, thread_id: str, timeout: float = 60.0) -> list[dict[str, Any]]:
        if self._proc is None or self._proc.stdout is None:
            raise CodexBridgeError("Codex app-server is not running")
        events: list[dict[str, Any]] = []
        end = time.time() + timeout
        while time.time() < end:
            message = self._read_message()
            events.append(message)
            if (
                message.get("method") == "thread/status/changed"
                and message.get("params", {}).get("threadId") == thread_id
                and message.get("params", {}).get("status", {}).get("type") == "idle"
            ):
                return events
        raise CodexBridgeError("Timed out waiting for Codex thread to return to idle")

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if self._proc is None or self._proc.stdin is None:
            raise CodexBridgeError("Codex app-server is not running")

        request_id = self._next_id
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

        while True:
            message = self._read_message()
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise CodexBridgeError(str(message["error"]))
            return message.get("result", {})
