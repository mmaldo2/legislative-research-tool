"""The guarded code conduit (_exec_sandboxed_python) -- the honest baseline's compute tool, now a
`--network none` Docker container (Architecture B, the harness-lift integrity gate).

Two layers:
  - HERMETIC (no Docker): `_classify_sandbox_exit` maps a finished container's (rc, stdout, stderr)
    to a SandboxResult -- the always-on coverage of timeout/OOM/start-failure/script-error handling.
  - `requires_docker`: the REAL container -- stdlib compute, NO db driver, and the load-bearing
    integrity assertion that the sandbox has ZERO network egress (it cannot reach our Postgres).
"""

import json
import shutil
import subprocess

import pytest

from lab.solvers import (
    SandboxResult,
    _build_sandbox_inputs,
    _classify_sandbox_exit,
    _exec_sandboxed_python,
    _ext_for,
    _sandbox_argv,
)


# --- hermetic: the exit-code classifier (no Docker needed) ------------------------------------
def _c(rc, stdout="", stderr="", timeout_s=15.0, cap=10000):
    return _classify_sandbox_exit(rc, stdout, stderr, timeout_s=timeout_s, cap=cap)


def test_classify_success_output():
    assert _c(0, "4\n").text == "4"
    assert _c(0, "").text == "(no output)"


def test_classify_appends_stderr():
    out = _c(0, "result", "a warning").text
    assert "result" in out and "[stderr]" in out and "a warning" in out


def test_classify_timeout_is_script_limit_not_infra():
    r = _c(124, timeout_s=2.0)
    assert "time limit" in r.text and r.infra_error is None  # agent-visible, NOT excluded


def test_classify_oom_is_infra():
    r = _c(137)
    assert r.infra_error == "oom"  # excluded


def test_classify_docker_start_failure_is_infra():
    assert _c(125).infra_error == "sandbox_start"
    assert _c(2, stderr="python: can't open file '/sandbox/code.py'").infra_error == "sandbox_start"


def test_classify_script_error_is_not_infra():
    r = _c(1, stderr="Traceback ... ValueError")
    assert r.infra_error is None and "ValueError" in r.text  # the agent's bug, scored normally


def test_classify_caps_output():
    assert len(_c(0, "x" * 100000, cap=500).text) <= 1000


# --- hermetic: the run_python @tool tags apparatus failures for exclusion --------------------
async def test_run_python_tool_marks_infra(monkeypatch):
    """An apparatus failure -> the observation carries error_kind='sandbox_infra' (which the solver
    reads to set result_subtype, excluding the rollout). The panel's dominant blocker."""
    from lab import solvers

    async def fake_exec(code, **kw):
        return solvers.SandboxResult("Failed: sandbox down", infra_error="docker_unavailable")

    monkeypatch.setattr(solvers, "_exec_sandboxed_python", fake_exec)
    obs: list = []
    await solvers._make_run_python_tool(obs).handler({"code": "print(1)"})
    assert obs[-1]["error_kind"] == "sandbox_infra"
    assert obs[-1]["result"] == "Failed: sandbox down"


async def test_run_python_tool_no_infra_on_success(monkeypatch):
    from lab import solvers

    async def fake_exec(code, **kw):
        return solvers.SandboxResult("42")

    monkeypatch.setattr(solvers, "_exec_sandboxed_python", fake_exec)
    obs: list = []
    await solvers._make_run_python_tool(obs).handler({"code": "print(42)"})
    assert "error_kind" not in obs[-1] and obs[-1]["result"] == "42"


# --- hermetic: data injection (/sandbox/inputs/) is built ONLY from observations ---------------
def test_build_sandbox_inputs_dumps_data_observations():
    """observations.json carries the DATA-bearing tool RESULTS; run_python's own output + submit
    acks are excluded (no recursive injection); fetched files pass through verbatim."""
    obs = [
        {"tool": "get_member_voting_record", "arguments": {"person_id": "p1"}, "result": "REC-A"},
        {"tool": "fetch_url", "arguments": {"url": "https://x/y.csv"}, "result": "saved -> f1.csv"},
        {"tool": "run_python", "arguments": {"code": "print(1)"}, "result": "1"},  # excluded
        {"tool": "submit_answer", "arguments": {"yea": 1}, "result": "recorded"},  # excluded
    ]
    inputs = _build_sandbox_inputs(obs, {"fetch_1.csv": "a,b\n1,2\n"})
    assert inputs["fetch_1.csv"] == "a,b\n1,2\n"
    data = json.loads(inputs["observations.json"])
    assert [d["tool"] for d in data] == ["get_member_voting_record", "fetch_url"]
    assert data[0]["result"] == "REC-A"


def test_build_sandbox_inputs_no_gold_leak():
    """THE no-gold-leak guard: the injected payload is a function of observations + fetched files
    ONLY -- it never receives inst.gold/inst.params, so the answer cannot reach the sandbox."""
    gold_sentinel = "GOLD-7f3a-SECRET"
    obs = [{"tool": "get_vote_event", "arguments": {"vote_event_id": "e1"}, "result": "yea/nay"}]
    blob = "".join(_build_sandbox_inputs(obs, {}).values())
    assert gold_sentinel not in blob  # the function has no parameter through which gold could enter


def test_build_sandbox_inputs_empty_when_no_data():
    assert _build_sandbox_inputs([], {}) == {}
    assert "observations.json" not in _build_sandbox_inputs(
        [{"tool": "run_python", "arguments": {}, "result": "x"}], {}
    )


def test_ext_for_prefers_content_type_then_suffix():
    assert _ext_for("https://x/data", "text/csv; charset=utf-8") == "csv"
    assert _ext_for("https://x/a.json", None) == "json"
    assert _ext_for("https://x/page", "text/html") == "html"
    assert _ext_for("https://x/no/suffix", None) == "txt"
    assert _ext_for("https://x/weird.toolongsuffix", None) == "txt"  # bounded to <=5 alnum


def test_sandbox_argv_locks_down_and_forbids_dangerous_flags():
    """The forbidden-flags argv check (security-sentinel gate): the egress + privilege lockdown is
    present and NO escape flag is."""
    argv = _sandbox_argv("sbx-test", "/tmp/stage", timeout_s=15.0)
    joined = " ".join(argv)
    # the integrity-bearing flags ARE present
    assert argv[argv.index("--network") + 1] == "none"  # zero egress (never 'host')
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--user") + 1] == "1000:1000"  # non-root
    assert "no-new-privileges" in argv and "--read-only" in argv
    assert "/tmp/stage:/sandbox:ro" in argv  # the SOLE mount, read-only
    # NO escape / host-access flags anywhere in the argv
    assert "--privileged" not in argv
    assert "--cap-add" not in argv  # nothing re-added after --cap-drop ALL
    assert not any(a == "--pid" or a.startswith("--pid=") for a in argv)
    assert not any(a == "--network=host" for a in argv)
    assert "-e" not in argv and "--env" not in argv  # no host env forwarded
    assert "docker.sock" not in joined  # the daemon socket is never mounted


# --- requires_docker: the real container ------------------------------------------------------
def _require_docker():
    if shutil.which("docker") is None:
        pytest.skip("docker not on PATH")
    try:
        if subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode != 0:
            pytest.skip("docker daemon not available")
    except Exception as exc:  # noqa: BLE001 -- unavailable means skip, not fail
        pytest.skip(f"docker unavailable: {exc}")


@pytest.mark.requires_docker
async def test_runs_stdlib_compute():
    _require_docker()
    r = await _exec_sandboxed_python(
        "import json, statistics; print(json.dumps(statistics.mean([2,4,6])))"
    )
    assert isinstance(r, SandboxResult) and r.infra_error is None
    assert r.text.strip().startswith("4")


@pytest.mark.requires_docker
async def test_no_db_driver_importable():
    """Stdlib-only image -> the postgres drivers cannot be imported (the agent code has no
    in-process path to our DB even before the network block)."""
    _require_docker()
    out = (await _exec_sandboxed_python("import psycopg2")).text
    assert "ModuleNotFoundError" in out or "No module named" in out


@pytest.mark.requires_docker
async def test_zero_network_egress():
    """THE integrity assertion: `--network none` -> the sandbox cannot open ANY socket, so it can
    never reach our Postgres / API. A reachable socket here is a gate failure."""
    _require_docker()
    code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 443), timeout=4); print('REACHED-NET')\n"
        "except OSError as e:\n"
        "    print('BLOCKED', type(e).__name__)\n"
    )
    out = (await _exec_sandboxed_python(code, timeout_s=10)).text
    assert "REACHED-NET" not in out
    assert "BLOCKED" in out


@pytest.mark.requires_docker
async def test_timeout_is_enforced_and_not_infra():
    _require_docker()
    r = await _exec_sandboxed_python("import time; time.sleep(30)", timeout_s=2.0)
    assert "time limit" in r.text and r.infra_error is None


@pytest.mark.requires_docker
async def test_output_is_capped():
    _require_docker()
    r = await _exec_sandboxed_python("print('x' * 100000)", cap=500)
    assert len(r.text) <= 1000  # capped (allowing for the optional [stderr] suffix headroom)


@pytest.mark.requires_docker
async def test_oom_is_excludable_infra():
    """A memory blow-up is SIGKILLed by the cgroup (exit 137) and surfaced as infra (excluded), not
    scored as a wrong answer."""
    _require_docker()
    r = await _exec_sandboxed_python("x = bytearray(4 * 1024 * 1024 * 1024); print(len(x))")
    assert r.infra_error == "oom"


@pytest.mark.requires_docker
async def test_inputs_are_mounted_readonly():
    """Injected files land under /sandbox/inputs/ for the agent's run_python to read (the data-
    injection channel that replaces the SDK host tool-result cache)."""
    _require_docker()
    r = await _exec_sandboxed_python(
        "print(open('/sandbox/inputs/data.txt').read().strip())",
        inputs={"data.txt": "hello-from-mount"},
    )
    assert r.text.strip() == "hello-from-mount" and r.infra_error is None


@pytest.mark.requires_docker
async def test_inputs_mount_is_not_writable():
    """The mount is `:ro` -> the agent's code cannot tamper with its injected data (defense in
    depth; a write attempt errors, it does not silently persist)."""
    _require_docker()
    r = await _exec_sandboxed_python(
        "import os\n"
        "try:\n"
        "    open('/sandbox/inputs/x.txt', 'w').write('nope'); print('WROTE')\n"
        "except OSError as e:\n"
        "    print('READONLY', e.errno)\n"
    )
    assert "WROTE" not in r.text and "READONLY" in r.text


@pytest.mark.requires_docker
async def test_run_python_tool_reads_injected_observations():
    """END-TO-END (the real @tool + a real container): the agent's prior tool RESULTS are injected
    as inputs/observations.json, so a run_python script computes over data it never had to retype
    into `code` -- the fix for the smoke's over-refusal when the SDK spilled a large result."""
    from lab.solvers import _make_run_python_tool

    _require_docker()
    observations = [
        {"tool": "get_member_voting_record", "arguments": {"person_id": "p1"}, "result": "yea yea"}
    ]
    run_python = _make_run_python_tool(observations, {})
    code = (
        "import json\n"
        "d = json.load(open('/sandbox/inputs/observations.json'))\n"
        "print(d[0]['result'].split().count('yea'))\n"
    )
    out = await run_python.handler({"code": code})
    text = out["content"][0]["text"]
    assert text.strip() == "2"
    assert "error_kind" not in observations[-1]  # the run_python obs (no infra failure)
