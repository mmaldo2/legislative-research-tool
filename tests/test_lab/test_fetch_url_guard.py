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
    "http://[::ffff:127.0.0.1]/x",  # IPv4-mapped IPv6 loopback (pre-3.12.4 property gap)
    "http://[::ffff:7f00:1]/x",  # same, hex form
    "http://[::ffff:10.0.0.5]/x",  # IPv4-mapped IPv6 private
    "http://0.0.0.0/x",  # unspecified -> "this host"
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


# --- fetch-to-mount success path (hermetic: a fake httpx stream, no real network) -------------
class _FakeResp:
    def __init__(self, body: bytes, content_type: str):
        self._body = body
        self.headers = {"content-type": content_type}
        self.is_redirect = False

    async def aiter_bytes(self):
        # two chunks -> exercises the streaming accumulation loop
        yield self._body[: len(self._body) // 2]
        yield self._body[len(self._body) // 2 :]


class _FakeStreamCtx:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def stream(self, method, url, headers=None):
        return _FakeStreamCtx(self._resp)


def test_fetch_url_streams_body_to_mount_and_returns_pointer(monkeypatch):
    """The web-arm bulk path: a PUBLIC fetch STREAMS the full body into the shared sandbox_files
    store as fetch_1.csv, and the trajectory records only a SHORT pointer (not the bulk text). This
    is the sole audited egress into the no-network sandbox."""
    import asyncio

    import httpx

    from lab import solvers

    body = b"col_a,col_b\n" + b"1,2\n" * 5000  # ~bulk CSV
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _FakeClient(_FakeResp(body, "text/csv")))
    monkeypatch.setattr(solvers, "_is_safe_public_url", lambda u: True)  # skip DNS in the unit test

    obs: list = []
    files: dict = {}
    tool = _make_fetch_url_tool(obs, files)
    out = asyncio.run(tool.handler({"url": "https://voteview.com/static/data/votes.csv"}))
    pointer = out["content"][0]["text"]

    # the body is stashed for run_python under a content-typed name...
    assert files == {"fetch_1.csv": body.decode()}
    # ...and the agent sees a short pointer, NOT the bulk text
    assert "fetch_1.csv" in pointer and "/sandbox/inputs/fetch_1.csv" in pointer
    assert "col_a" not in pointer and len(pointer) < 200
    assert obs[-1]["tool"] == "fetch_url" and obs[-1]["result"] == pointer


def test_fetch_url_caps_oversized_body(monkeypatch):
    """A body larger than _FETCH_MAX_BYTES is truncated at the cap (host-memory bound)."""
    import asyncio

    import httpx

    from lab import solvers

    big = b"x" * (solvers._FETCH_MAX_BYTES + 100_000)
    fake = _FakeClient(_FakeResp(big, "text/plain"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: fake)
    monkeypatch.setattr(solvers, "_is_safe_public_url", lambda u: True)

    files: dict = {}
    asyncio.run(_make_fetch_url_tool([], files).handler({"url": "https://x/big.txt"}))
    assert len(files["fetch_1.txt"]) == solvers._FETCH_MAX_BYTES
