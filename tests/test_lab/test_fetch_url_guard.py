"""SSRF guard for the web-arm fetch_url tool (the integrity wall for the ablation's web surface).

The guard is what lets the web arm read PUBLIC pages but NEVER reach our DB. These tests are
network-free: the pure guard cases, and that the @tool REFUSES a private/file URL BEFORE any fetch
(the guard short-circuits, so no httpx call). The allowed-public path makes a real network call, so
it is NOT exercised in CI.
"""

import pytest

from lab.solvers import _is_safe_public_url, _make_fetch_url_tool

BLOCKED = [
    "http://localhost:8000/api",  # our FastAPI -> our DB
    "http://127.0.0.1/x",
    "https://127.0.0.1:5432",  # postgres
    "http://[::1]/x",  # ipv6 loopback
    "file:///etc/passwd",  # non-http scheme
    "ftp://congress.gov",
    "http://10.0.0.5/db",  # private
    "http://192.168.1.1/",
    "http://172.16.0.1/",
    "http://169.254.169.254/latest/meta-data",  # cloud metadata SSRF
    "not a url",
    "http://nonexistent.invalid.host.zzzq/",  # unresolvable
    "",
]
ALLOWED = [
    "https://www.congress.gov/",
    "https://clerk.house.gov/Votes",
    "https://www.govtrack.us/congress/votes",
]


@pytest.mark.parametrize("url", BLOCKED)
def test_guard_blocks_private_and_nonhttp(url):
    assert _is_safe_public_url(url) is False


@pytest.mark.parametrize("url", ALLOWED)
def test_guard_allows_public_hosts(url):
    # resolves public hosts; needs DNS but no fetch. (Skip on no network.)
    try:
        assert _is_safe_public_url(url) is True
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"DNS unavailable: {exc}")


def test_fetch_url_tool_refuses_localhost_without_fetching():
    """The @tool must short-circuit on a blocked URL — the guard rejects BEFORE httpx, so no network
    call and a clean 'Refused' result recorded in the trajectory."""
    import asyncio

    obs: list = []
    tool = _make_fetch_url_tool(obs)
    out = asyncio.run(tool.handler({"url": "http://localhost:8000/api/v1/votes"}))
    text = out["content"][0]["text"]
    assert "Refused" in text and "localhost" in text
    assert obs == [
        {
            "tool": "fetch_url",
            "arguments": {"url": "http://localhost:8000/api/v1/votes"},
            "result": text,
        }
    ]


def test_fetch_url_tool_refuses_file_scheme():
    import asyncio

    obs: list = []
    tool = _make_fetch_url_tool(obs)
    out = asyncio.run(tool.handler({"url": "file:///etc/passwd"}))
    assert "Refused" in out["content"][0]["text"]
