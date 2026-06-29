"""The guarded code conduit (_exec_sandboxed_python) -- the honest baseline's compute tool, now a
`--network none` Docker container (Architecture B, the harness-lift integrity gate).

Two layers:
  - HERMETIC (no Docker): `_classify_sandbox_exit` maps a finished container's (rc, stdout, stderr)
    to a SandboxResult -- the always-on coverage of timeout/OOM/start-failure/script-error handling.
  - `requires_docker`: the REAL container -- stdlib compute, NO db driver, and the load-bearing
    integrity assertion that the sandbox has ZERO network egress (it cannot reach our Postgres).
"""

import shutil
import subprocess

import pytest

from lab.solvers import SandboxResult, _classify_sandbox_exit, _exec_sandboxed_python


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
