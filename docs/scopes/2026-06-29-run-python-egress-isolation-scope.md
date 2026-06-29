---
date: 2026-06-29
topic: run_python egress isolation (the harness-lift integrity gate)
scope-mode: hold
status: approved
---

# Scope: run_python egress isolation

## Problem
The harness-lift web baseline ([[project_condorcet_experimental_design]]) only succeeds via a
`run_python` -> `urllib` -> voteview.com bulk-CSV path; the honest `fetch_url` path can't deliver
bulk data (20K-char cap) and times out. So `run_python` needs UNRESTRICTED network to be a strong
baseline -- but that same hole lets it reach OUR Postgres (`localhost:5432`) / API (`localhost:8000`).
Pilot proof: opus's `run_python` used `urllib` (bypassing the SSRF-guarded `fetch_url`). Before any
PUBLISHED number, the web arm must reach **public bulk data but NOT our data**. (Correctness, not
just security: a crippled baseline = the bias we defend against.)

## In Scope
- Re-back `_exec_sandboxed_python` to exec inside a **stdlib-only Docker Linux container** (Docker is
  running) instead of host `sys.executable`; keep the existing guards (`-I -S`, scrubbed env, temp
  cwd, timeout, output cap).
- **WEB arm:** egress **deny-rule** (block RFC1918 / loopback / link-local / Docker host-gateway /
  host.docker.internal / our hosts; ALLOW all other public). "Block-our-data-only" per the decision.
- **OURS arm:** `run_python` gets **NO network** (it only computes over already-retrieved records);
  design how its retrieved data reaches the no-network container (RO mount of the tool-result file vs
  inline-in-code).
- Tests: public host reachable from the web container; loopback/private/our-DB connect is REFUSED;
  ours container has zero egress. Keep the mechanical trace-grep as defense-in-depth.
- Rotate the local DB creds off the public `DEFAULT_DB_URL` default (`legis:legis_dev`).

## Out of Scope
- Explicit public-host allowlist (chose block-our-data-only). The full k=3 matrix run + the McNemar/
  cost/variance analysis script (next workstream). Raising `fetch_url`'s 20K cap (the container path
  supersedes it for bulk data). Non-Docker portability.

## Key Constraints
- Experiment-grade -> publication-grade gate; must run on THIS box (Windows 11 + Docker Desktop/WSL2).
- `lab/` only; in NEITHER frozen hash (`solvers.py` is uninvolved in grading). Per-rollout `docker run`
  latency (~hundreds ms-1s) acceptable for an experiment.

## Codebase Context
- `lab/solvers.py`: `_exec_sandboxed_python` (~L642, the exec to re-back), `_make_run_python_tool`
  (~L682), `_is_safe_public_url` (~L555, the deny-range precedent), `_sdk_tool_config` (~L833, the
  ours-vs-web branch that provisions run_python). `tests/test_lab/test_sandbox_exec.py` (update for
  the container path).

## Open Questions (for /ce:plan)
1. Container lifecycle: per-rollout `docker run` vs a pooled/long-lived sandbox reset between rollouts
   (latency vs isolation).
2. OURS data-passing into a no-network container: RO bind-mount of the SDK tool-result file vs the
   agent inlining data in `code` (and whether the SDK still spills large results to a host path).
3. Exact deny set incl. the Docker/WSL host-gateway IP + host.docker.internal; how to ASSERT it in a
   test (attempt a loopback/private connect -> blocked; a public connect -> allowed).
4. Image build/caching (stdlib-only `python:slim`); how the web container performs the bulk fetch
   (urllib inside the container, egress-filtered) and returns capped stdout.
5. DB-cred rotation mechanism (env/.env) without breaking the lab's own DB reads.
