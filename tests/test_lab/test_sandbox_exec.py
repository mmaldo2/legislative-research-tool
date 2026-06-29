"""The web-arm guarded code conduit (_exec_sandboxed_python) -- the honest baseline's compute tool.

Hermetic: spawns a real `python -I -S` subprocess (no DB, no network needed). These guards are what
keep the S+T / F+T baseline arm HONEST -- it must compute over scraped public data but must NOT be
able to reach our Postgres (which would understate harness lift and break the eval's defensibility).
"""

from lab.solvers import _exec_sandboxed_python


async def test_runs_stdlib_compute():
    """The standard library IS available -- the baseline can genuinely compute."""
    out = await _exec_sandboxed_python(
        "import json, statistics; print(json.dumps(statistics.mean([2, 4, 6])))"
    )
    assert out.strip().startswith("4")


async def test_scrubs_db_url_and_secrets():
    """DATABASE_URL and any *KEY*/*TOKEN*/ANTHROPIC* env vars must NOT survive into the sandbox."""
    out = await _exec_sandboxed_python(
        "import os; print('DBURL=', os.environ.get('DATABASE_URL')); "
        "print('SECRETS=', sorted(k for k in os.environ "
        "if 'KEY' in k.upper() or 'TOKEN' in k.upper() or k.upper().startswith('ANTHROPIC')))"
    )
    assert "DBURL= None" in out
    assert "SECRETS= []" in out


async def test_no_db_driver_importable():
    """`-S` drops site-packages -> the postgres drivers cannot be imported -> the baseline code has
    no path to our DB even if it tried (the load-bearing integrity guard)."""
    out = await _exec_sandboxed_python("import psycopg2")
    assert "ModuleNotFoundError" in out or "No module named" in out
    out2 = await _exec_sandboxed_python("import asyncpg")
    assert "ModuleNotFoundError" in out2 or "No module named" in out2


async def test_timeout_is_enforced():
    out = await _exec_sandboxed_python("import time; time.sleep(30)", timeout_s=2.0)
    assert "time limit" in out


async def test_output_is_capped():
    out = await _exec_sandboxed_python("print('x' * 100000)", cap=500)
    assert len(out) <= 1000  # capped (allowing for the optional [stderr] suffix headroom)
