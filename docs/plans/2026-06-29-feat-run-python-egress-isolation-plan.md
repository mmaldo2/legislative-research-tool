---
title: "feat(lab): run_python egress isolation — Docker-sandboxed code tool (harness-lift integrity gate)"
type: feat
status: completed
date: 2026-06-29
origin: docs/scopes/2026-06-29-run-python-egress-isolation-scope.md
---

# feat(lab): run_python egress isolation (the harness-lift integrity gate)

## Overview
Re-back the lab's `run_python` code tool to execute inside a **Docker Linux container** instead of a
host `python -I -S` subprocess, so the harness-lift web baseline can reach **public bulk data**
(VoteView et al.) but provably **cannot reach our data** (Postgres `localhost:5432`, API
`localhost:8000`). This is the integrity gate that unblocks any PUBLISHED lift number
([[project_condorcet_experimental_design]], pre-reg REV 4.3 + the pilot finding). `lab/` only; in
NEITHER frozen hash (`solvers.py` is not in the grading/content hash).

## Problem Statement
The n=6 pilot proved the web baseline only succeeds via `run_python` -> `urllib` -> voteview.com bulk
CSV (the honest `fetch_url` path times out — and is 20K-char capped, so it can't deliver bulk data).
So `run_python` NEEDS unrestricted network to be a STRONG baseline — but the current `python -I -S`
host subprocess has full stdlib network and can reach our Postgres/API (the gateway is private but
reachable as `host.docker.internal`). The `-S`/`-I`/scrubbed-env guards block DB *drivers* and creds
but NOT raw sockets/urllib. We need OS-level egress control: **block-our-data-only** (allow public,
drop private/loopback/link-local/host-gateway), per the user decision.

## Proposed Solution (Architecture B — adopted post-panel, 2026-06-29)
Execute the sandboxed Python in a per-call `docker run` with **ZERO network on BOTH arms**
(`--network none`); the web arm reaches bulk public data ONLY through the existing SSRF-guarded
`fetch_url` conduit, streamed to a file the no-network `run_python` reads. **Deny-by-default:** there
is no egress namespace for agent code to leak through, and the sole path to the public web is the
already-audited, DNS-rebinding-proof `fetch_url` (which itself cannot reach our private ranges). This
deletes the entire iptables / NET_ADMIN / IPv6 / entrypoint stack and erases the three fail-open paths
the panel found in the egress-filter design (Architecture A, now rejected — see Alternatives + Panel).

- **Both arms — the sandbox:** `run_python` runs `--network none` (zero egress), `--user sandbox`
  (non-root directly; no root/`runuser`/cap dance), `--cap-drop ALL`, `--security-opt
  no-new-privileges`, `--read-only` rootfs + tmpfs `/tmp`, `--rm`, `--memory <sized for the bulk
  parse>`, `--pids-limit`, NO `-e` host env. Keep the in-container guards (`python -I -S`, ephemeral
  cwd) for defense-in-depth. The wall-clock is enforced PRIMARILY by an in-container `timeout`, with a
  host `docker rm -f` backstop (see container-reap below).
- **WEB-arm bulk data:** a web-surface `fetch_url` variant STREAMS the full response body to
  `/sandbox/inputs/fetch_<n>.<ext>` in the RO-mount staging dir (cap raised for bulk, e.g. a few MB),
  returning a SHORT pointer to context ("saved N bytes to inputs/fetch_2.csv") instead of 20K of text.
  `run_python` reads it. `_is_safe_public_url` is UNCHANGED — fetch_url stays the SOLE, audited egress;
  private/our-data IPs remain blocked at the app layer. (OURS arm: no fetch_url; compute-only.)
- **Data injection (both arms):** the rollout's accumulated tool outputs (`observations`) + any
  fetched files are written to a host staging dir, bind-mounted **read-only** at `/sandbox/inputs/`;
  the tool description tells the agent its retrieved data + fetched files live there and the sandbox
  has no host/network access. (Replaces the pilot's reliance on the SDK host tool-result cache.)
- **Infra failures are EXCLUDABLE (the panel's dominant blocker):** `_exec_sandboxed_python`
  distinguishes Docker-absent / image-missing / daemon-error / OOM (exit 137) / sandbox-timeout from
  script output, returns an infra sentinel, and the solver propagates `result_subtype="sandbox_infra"`
  so the matrix EXCLUDES those rollouts — never scoring an apparatus failure as a refusal/miss
  (which would fabricate pro-harness lift).
- **Container reap:** unique `--name sbx-<uuid>` (or `--cidfile`); a `finally` catching `TimeoutError`
  AND `CancelledError` runs `docker rm -f` (killing the `docker run` client does NOT stop the
  container — verified). Under `--network none` a leaked container has no egress, so this is a
  resource-hygiene fix, not an integrity hole.
- **Image:** built in a `run_ablation` **pre-flight** (fail-fast, never lazy-built inside a rollout),
  base **pinned by digest**, rebuilt on a `Dockerfile` hash mismatch, image ID **stamped into run
  metadata** (k=3 reproducibility).
- **Fail closed:** Docker unavailable -> `run_python` REFUSES via the infra sentinel (never host-exec
  fallback — that would silently reintroduce the hole).
- DB-cred rotation is **DEFERRED defense-in-depth** under B (deny-by-default egress already blocks the
  path); if done later, rotate via `ALTER ROLE` (NOT compose `POSTGRES_PASSWORD`, a no-op on the
  initialized volume) + update `.env` + assert the literal default fails to authenticate. The
  mechanical trace-grep stays as a tripwire (token driven from the current secret, not a stale literal).

## Technical Approach

### Architecture (B — deny-by-default)
```
WEB egress (the ONLY path to the web): fetch_url (SSRF-guarded, _is_safe_public_url)
        |  streams full body -> host staging dir/fetch_<n>.<ext>  (private IPs still blocked)
        v
_make_run_python_tool(observations)            # BOTH arms; no network param needed
        |  writes code.py + observations + fetched files -> host staging dir (RO mount)
        v
_exec_sandboxed_python(code, *, inputs_dir, timeout_s, cap)
        |  docker run --rm --name sbx-<uuid> --network none --user sandbox
        |    --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp
        |    --memory <sized> --pids-limit 128 -v <staging>:/sandbox:ro  <image@sha256:...>
        |    python -I -S /sandbox/code.py        (in-container `timeout` = primary wall-clock)
        v
stdout captured + capped; exit 137 / daemon-error / image-missing -> INFRA SENTINEL
        -> solver sets result_subtype="sandbox_infra" -> matrix EXCLUDES the rollout
host backstop: finally { docker rm -f sbx-<uuid> } on TimeoutError | CancelledError
```
`--network none` removes the egress namespace entirely (verified) -> no iptables, no gateway-IP
reasoning, no IPv6 carve-outs, no privilege dance. Our PG/API are simply unreachable (no interface);
the web arm's only web access is the audited `fetch_url`, which app-blocks private/loopback/reserved.

### New files
- **`lab/sandbox/Dockerfile`** — `FROM python:3.12-slim@sha256:<pinned>`; create an unprivileged
  `sandbox` user; NO iptables, NO entrypoint script (network is `none`; container runs `--user
  sandbox` directly). Stdlib-only (no pip installs -> no DB driver, preserving the
  `test_no_db_driver_importable` guarantee at the image level too).
- **`lab/sandbox/build.md`** + a `_ensure_image()` pre-flight helper — `docker build` tagged with a
  hash of `Dockerfile`; rebuild-on-mismatch; resolve + record the image ID for run metadata. (Shell
  builds must use forward-slash paths / `Path(d).as_posix()` — Git-Bash MSYS path-mangling is a
  shell artifact, NOT in the `create_subprocess_exec` code path — verified.)

### Implementation Phases (revised post-panel: egress + its proving assertions land together)

#### Phase 1: Container exec backend + excludable failures + reap — DONE (commit b8aaf43)
- [x] ~~Add `lab/sandbox/Dockerfile`~~ **SIMPLIFIED (Architecture B): no custom image** — the custom
      Dockerfile existed for iptables (Arch A); B needs only a stock interpreter, so we use the
      digest-pinned `python:3.12-slim@sha256:423ed6...` directly with `--user 1000:1000`.
      `ensure_sandbox_image()` is the pre-flight (pull-if-missing, fail-fast; the digest IS the pin,
      printed in the run header as the stamp).
- [x] Re-backed `_exec_sandboxed_python` to `docker run --network none --user 1000:1000 --cap-drop
      ALL --security-opt no-new-privileges --read-only --tmpfs /tmp --memory 1g --pids-limit 256 --rm
      --name sbx-<uuid> -v <staging>:/sandbox:ro` + in-container `timeout`; `finally`-reap (`docker rm
      -f`) on `TimeoutError`/`CancelledError`; capture + cap stdout. (Verified on-box: 0 leaks.)
- [x] **Infra-failure sentinel + exclusion:** `_classify_sandbox_exit` (PURE) maps Docker-absent /
      image-missing / OOM (137) / mount (rc2/125) -> `SandboxResult.infra_error`; `_make_run_python_tool`
      tags the obs `error_kind="sandbox_infra"`; `_asolve_sdk` sets `result_subtype="sandbox_infra"`;
      `ablation` routes it to the excluded `errored` bucket. Script `timeout`(124) is agent-visible,
      NOT excluded. Fail-closed when Docker absent (infra sentinel; no host fallback).
- [x] `requires_docker` marker registered + skip helper; `test_sandbox_exec.py` = hermetic
      `_classify_sandbox_exit` + @tool infra-marking (the always-on guard variant) + requires_docker
      real-container (stdlib compute, NO db driver, **ZERO network egress**, timeout-not-infra,
      OOM-is-infra, output cap, RO inputs mount). 14/14 green; 251 lab suite green; hashes unmoved.

#### Phase 2: Web fetch-to-mount + data injection + egress assertions (STOP for review)
- [x] Web-surface `fetch_url` variant: STREAMS the full body (capped `_FETCH_MAX_BYTES`=8MB) into
      the shared `sandbox_files` as `fetch_<n>.<ext>` (`_ext_for`: content-type then URL suffix),
      returns a SHORT pointer to context (not the bulk text); every redirect hop re-guarded by the
      UNCHANGED `_is_safe_public_url`. Hermetic success + cap tests (fake httpx stream).
- [x] Inject `observations` (+ fetched files) as RO `/sandbox/inputs/` via `_build_sandbox_inputs`
      (`observations.json` = data-bearing tool RESULTS; excludes run_python self + submit acks);
      `_RUN_PYTHON_DESC` points the agent at `/sandbox/inputs/` and states NO network/DB/cred access.
      `_sdk_tool_config` shares one `sandbox_files` store; web = fetch_url + run_python, ours =
      run_python only; both `--network none` (one exec path).
- [x] `requires_docker` BLOCKING egress assertions (run, not skipped, on this box — Docker live):
      `test_zero_network_egress` (run_python `socket.create_connection` blocked, both arms share the
      exec path); `test_inputs_mount_is_not_writable` (RO); `test_run_python_tool_reads_injected_
      observations` (end-to-end injection); `fetch_url` REFUSES private/loopback (hermetic, no fetch).
      No-gold-leak guard asserted (`test_build_sandbox_inputs_no_gold_leak` — the function has no
      gold/params parameter). Forbidden-flags argv check (`test_sandbox_argv_locks_down_and_forbids_
      dangerous_flags`: `--network none`, RO sole mount, NO `--privileged`/`--pid=host`/`--cap-add`/
      `-e`/docker.sock). **security-sentinel agent review** dispatched. STOP after findings addressed.
      NOTE: the live PUBLIC `fetch_url` round-trip (VoteView) is validated in Phase 3's re-pilot (real
      egress) rather than a flaky networked unit test; the streaming/cap/stash logic is proven
      hermetically here.

#### Phase 3: Re-pilot BOTH arms + regression-check (validate the gate is neutral) — DONE
- [x] Re-ran member_summary (`lift.member_summary_118house`) n=6 seed=42 BOTH arms under isolation
      (agent-sdk). **ours (haiku): 100% (6/6), 40s, $0.16** — parity vs PR #51 (100%/28s/$0.09); the
      injection path is exercised live (find_people -> get_member_voting_record -> run_python x4-7
      reading /sandbox/inputs/ -> submit) in 6/6, so the smoke's over-refusal is fixed. **web (opus):
      100% (6/6), 65s, $0.60** — NO drop vs PR #51's 33% (it IMPROVED: the structured fetch-to-mount
      conduit is a better honest path than urllib-flailing-in-sandbox). A probe CANNOT reach our DB:
      the mechanical trace-grep (`legis:`/`legis_dev`/`@localhost`/`:5432`/`localhost:8000`/`psycopg2`
      /`asyncpg`/`connect(`) is EMPTY across all web traces; web reaches VoteView ONLY via the audited
      fetch_url (3 fetches: members/rollcalls/votes CSVs).
      **REV 4.4 sizing fix (Phase-3 caught it):** the first probe (opus x web n=2) failed 0/2 / 100%
      timeout because fetch_url TRUNCATED H118_votes.csv at the 8MB cap (real file 14,621,369 B ~=
      14.6MB). PR #51's web arm used unbounded urllib-in-code, so the cap was a NEW gate artifact ->
      raised `_FETCH_MAX_BYTES` 8MB->32MB + `_SANDBOX_MEM` 1g->2g; re-probe 2/2, then full n=6 6/6.
      The votes matrix now arrives complete (14.6MB < 32MB cap) in all 6.
      **Headline preview (pre-reg REV 4.4):** at accuracy PARITY (100%/100%), ours(haiku) is ~3.75x
      cheaper ($0.16 vs $0.60) and faster (40s vs 65s) than web(opus) — the cost/reliability story,
      with a STRONG (not strawmanned) honest web baseline, which defends the bias critique. Unblocks
      the full matrix (haiku+sonnet x {ours,web} + opus x web, k=3). NOTE the ours n=6 was run pre-
      REV-4.4 but is apparatus-invariant to it (ours never fetches; its single-member parse is far
      under even the old 1g).
- [ ] (Deferred, defense-in-depth) DB-cred rotation via `ALTER ROLE` + `.env`; assert the literal
      `legis_dev` default fails to auth; confirm NO frozen/precompute/`autoresearch` hardcoded-default
      path breaks. Not required for the gate under B (egress is deny-by-default).

## System-Wide Impact
- **Interaction graph:** (web) `fetch_url` -> stream body to staging dir; `run_python` @tool ->
  staging-dir write (code + observations + fetched files) -> `docker run --network none --user
  sandbox` -> `python -I -S /sandbox/code.py` -> stdout captured -> observation recorded. The
  `_sdk_tool_config` ours/web branch differs ONLY in whether `fetch_url` is provisioned; `run_python`
  is network-none on both.
- **Error propagation:** Docker missing/image absent / OOM(137) / daemon-error / sandbox-timeout ->
  INFRA SENTINEL -> `result_subtype="sandbox_infra"` -> matrix EXCLUDES (never a trust-fatal grade).
  Script nonzero/stderr -> returned as text (unchanged contract). Timeout -> in-container `timeout`
  stops the script; `finally docker rm -f` (on `TimeoutError`/`CancelledError`) reaps the container
  (killing the client alone does NOT — verified); staging dir cleaned (`ignore_cleanup_errors`).
- **State lifecycle:** per-call container `--rm` + `--read-only` + tmpfs + ephemeral staging -> no
  cross-rollout bleed; unique `--name` avoids collisions; staging dir removed after each call.
- **API surface parity:** BOTH arms route through the SAME `_exec_sandboxed_python` (one code path,
  always `--network none`); they differ ONLY in whether `fetch_url` is offered + what lands in the
  mount. No second exec path to drift.
- **Integration scenarios (the requires_docker tests):** both-arms-zero-egress (run_python);
  fetch_url-reaches-public + refuses-private; fetch-to-mount delivers a bulk body run_python reads;
  DB-driver-still-unimportable; infra-failure -> excluded (not scored); container-reap-on-timeout;
  injected file carries no gold; oversized observations bounded.

## Acceptance Criteria
- [x] `run_python` executes `--network none --user sandbox` in a digest-pinned Docker container (both
      arms); existing guard tests pass through it (`requires_docker`) + a thin hermetic variant
      survives Docker-less CI; fail-closed via the infra sentinel when Docker is absent.
- [x] BOTH sandboxes have ZERO egress (asserted: `socket.create_connection` fails); the web arm
      reaches public data ONLY via `fetch_url`, which still REFUSES private/loopback URLs and streams
      bulk public bodies to the RO mount.
- [x] Infra failures (Docker/image/OOM/daemon/timeout) surface as `result_subtype="sandbox_infra"` and
      are EXCLUDED by the matrix — never scored as `over_refusal`/`hallucination`.
- [x] Timed-out/cancelled containers are force-removed (`docker ps -a` flat across a run; client also
      killed); image ensured in pre-flight, pinned by digest, digest stamped into the run header.
- [x] Retrieved data injected at `/sandbox/inputs/`; asserted built ONLY from `observations` (no
      `gold`/`params` leak). Forbidden docker flags absent (argv check); no host `-e` env.
- [x] `grading_contract_hash` / `content_hash` unmoved; `ruff` clean; full lab suite green
      (Docker-dependent tests skip cleanly where Docker is absent, but BLOCK on the box producing
      published numbers).
- [x] Phase-3 re-pilot: BOTH arms validated under isolation (ours 6/6; web 6/6 reaches VoteView via
      fetch-to-mount + computes; mechanical trace-grep EMPTY -> no probe reached our DB); web
      completion/cost/latency NOT regressed vs PR #51 (33%/237s/$1.26 -> 100%/65s/$0.60 — improved).

## Alternatives Considered
- **Architecture A — iptables egress-filter on a networked web container** (the original plan):
  REJECTED post-panel. Feasible (lens 2 verified on this box) but **allow-by-default with three
  fail-OPEN paths** (failed-iptables-insert runs open; `NET_ADMIN`+setuid-regain flushes the rules;
  IPv6 leak) + breaks `runuser` without SETUID/SETGID + needs baked iptables + IPv6 policy + a
  fail-closed self-verifying entrypoint. B achieves a STRONGER (deny-by-default) gate with far less
  surface. A's only edge — ecological validity (the pilot's natural `urllib`-in-code) — judged
  non-binding: B still reaches all public data via the audited conduit. (User chose B.)
- **Forward-proxy allowlist** (explicit public-host list): rejected — user chose block-our-data-only;
  more infra (a proxy sidecar) for a stricter policy we did not pick.
- **WSL2 + nftables on the host VM:** rejected — ties to the WSL setup, harder to assert/port than
  in-container iptables; Docker is already running.
- **Host subprocess + proxy env + socket block:** rejected — a host process can ignore proxy env and
  open raw sockets; weak without OS enforcement (least defensible).
- **Inline data (no mount):** rejected — 1210-record payloads can't be reliably copied into `code`;
  the RO mount is why the SDK disk-cache dependency existed.

## Risks & Mitigations
- **Per-call `docker run` latency** (verified ~0.28s `--network none` warm; ~3-4 calls/rollout):
  negligible vs 30–150s rollouts; a matrix-start warm-up `docker run` catches a missing image early.
  Pooling deferred (YAGNI). NOTE the latency is bounded by `--network none` (no iptables/bridge setup).
- **`--memory` OOM-kills the VoteView bulk parse** (lens 5): size `--memory` against the real
  fetch-to-mount workload; map exit 137 to the infra sentinel (not "(no output)"); the Phase-3
  regression check is the gate on sizing.
- **Bind-mount silently empty on Docker Desktop** if the staging dir isn't on a shared path (lens 5):
  pre-check `/sandbox/inputs/` non-empty -> infra sentinel if not; `requires_docker` test for the
  injected-data path. Use `Path(d).as_posix()` for mount sources.
- **Requiring Docker reduces hermeticity** of the sandbox tests: accepted — OS isolation needs the OS
  mechanism; tests gated `requires_docker` (mirrors `requires_pg`), but KEEP a thin hermetic guard
  variant + BLOCK (not skip) the egress assertions on the box producing published numbers.
- **Determinism:** pin the base image by digest + stamp the image ID into run metadata so k=3 reps +
  ours-vs-web cells share identical apparatus (lens 5).
- **Integrity is security-critical:** require a **security-sentinel** pass before the gate is trusted
  for any PUBLISHED number (the scope's stated gate). (Architecture B's deny-by-default posture +
  audited single conduit is what makes this pass-able; the rejected A had three fail-open paths.)

## Panel synthesis (5-lens, 2026-06-29) — one architecture decision + 6 mechanism-independent blockers
Five adversarial reviewers (security, Docker/Windows feasibility [verified on this box], experimental
validity, simplicity, operational). The container + fail-closed CORE is affirmed by all five; the
`--network none` OURS arm drew ZERO findings. But the plan as written (iptables egress-FILTER on web)
is **allow-by-default with multiple fail-OPEN paths**, and several blockers are mechanism-independent.

### THE DECISION (resolve first — it determines ~60% of the build): egress-filter vs deny-by-default
- **Option A — iptables egress-filter (the plan as written).** FEASIBLE: lens 2 verified on this box
  (public 1.1.1.1:443 OK, host.docker.internal `192.168.65.254`:5432 blocked, ~0.45s). BUT lens 1
  found it **fail-OPEN three ways** unless each is fixed: (B-A1) entrypoint must `set -euo pipefail` +
  self-verify the DROP rules and `exit 1` BEFORE running user code (slim ships iptables-nft; a failed
  insert silently runs with open egress); (B-A2) `NET_ADMIN` survives the bounding set + slim has
  setuid-root binaries -> agent code can regain root and flush the firewall -> need
  `--security-opt=no-new-privileges` + `capsh --drop=cap_net_admin`; (B-A3) IPv6 must be MANDATORY
  (disable_ipv6 or full ip6tables), not a footnote. Plus lens 2: `--cap-drop ALL --cap-add NET_ADMIN`
  **breaks `runuser`** ("cannot set groups") -> also need `--cap-add SETUID --cap-add SETGID`; iptables
  must be **baked in the image** (runtime apt fails under `--read-only`).
- **Option B — `--network none` on BOTH arms + bulk-fetch-to-mount (lens 4, recommended).** run_python
  gets ZERO egress on both arms; the WEB arm obtains bulk public data through the EXISTING
  SSRF-guarded `fetch_url` (`_is_safe_public_url`, already DNS-rebinding-proof + tested) in a variant
  that STREAMS the body to a file in the RO mount (cap raised for bulk; a short note returned to
  context), which run_python then reads. This is **deny-by-default**: it DELETES the entire iptables /
  NET_ADMIN / SETUID / ip6tables / entrypoint / baked-iptables stack AND erases lens-1 B-A1/2/3 (no
  egress namespace to leak through; the only egress is the audited conduit). Container-leak-on-timeout
  (below) also stops being an integrity hole (a leaked `--network none` container can't reach our DB).
- **The ONLY cost of B is ecological validity** (lens 4's one real counter, echoed by lens 3): the
  pilot's opus naturally used `urllib`-in-run_python; forcing fetch-tool-then-read is a slightly
  different tool surface that a reviewer COULD call a "crippled baseline." Rebuttal: B still reaches
  ALL public data (any public URL via fetch_url), only the API shape changes; sandboxed-compute +
  a fetch-tool is arguably the MORE standard agent setup, not a weaker one. **Recommendation: B**
  (deny-by-default is the defensible posture for a publication-grade gate), pre-registering the
  fetch-to-mount baseline explicitly. Decision is the user's (it defines the pre-registered baseline).

### Mechanism-INDEPENDENT blockers (apply to A or B; fold in regardless)
- [BLOCKER] **Infra failures must be EXCLUDABLE, not scored as misses** (lens 3 + lens 5, the dominant
  finding). Docker-down / image-missing / OOM (exit 137) / mount-empty / sandbox-timeout currently
  return an in-band string -> set NEITHER `errored` NOR `result_subtype` -> `classify()` scores them
  as `over_refusal`/`hallucination`, **fabricating pro-harness lift**. Fix: `_exec_sandboxed_python`
  returns a distinct infra-error sentinel; the tool/solver propagates it to a new excludable signal
  (a `result_subtype="sandbox_infra"` or an additive flag) so the matrix drops those rollouts. This is
  the integrity-of-the-MEASUREMENT gate and is required for any published number.
- [BLOCKER] **Container reap on timeout/cancel** (lens 1, 2 [verified], 5). `proc.kill()` kills the
  `docker run` CLIENT, not the container -> it keeps running (under A, with live egress; orphans
  accumulate over ~600 rollouts -> exhaust WSL2). Fix: unique `--name`/`--cidfile`; `finally` that
  catches `TimeoutError` AND `CancelledError` -> `docker rm -f`; prefer in-container `timeout` as the
  primary control + `docker rm -f` backstop.
- [BLOCKER] **Image pre-flight, not lazy-build-in-rollout; pin + stamp** (lens 5). Build in a
  `run_ablation` pre-flight (fail-fast), pin the base by digest, rebuild-on-`Dockerfile`/`entrypoint`
  hash-mismatch, and record the image ID in run metadata (k=3 reproducibility).
- [BLOCKER] **`--memory` sized for the bulk path + OOM visible** (lens 5). 512m likely OOM-kills the
  VoteView load (exit 137 -> currently "(no output)"). Size against the real workload; map 137 to the
  infra-exclusion sentinel above.
- [BLOCKER] **Re-pilot BOTH arms + regression-check vs PR #51** (lens 3). Ours also changes (disk-cache
  -> injected file). Require ours ~6/6 and web completion/cost/latency statistically indistinguishable
  from the merged pilot; a material web drop = the gate distorting the measurement -> block.
- [BLOCKER] **Cred rotation: `ALTER ROLE`, not compose** (lens 1, verified reasoning). `POSTGRES_PASSWORD`
  only applies on first volume init; the `pgdata` volume is already initialized -> editing compose is
  a no-op and the acceptance criterion would be silently false. Rotate the live role + update `.env`;
  test that the literal default fails to auth; verify NO frozen/precompute/`autoresearch` hardcoded-
  default path breaks (lens 3). Under B, cred-rotation is DEFER-able defense-in-depth (lens 4).

### Should-fixes
- Assert (requires_docker test) the injected file is built ONLY from `observations` (tool RESULTS),
  never `inst.gold`/`inst.params` — the concrete no-gold-leak guard (lens 1, 3).
- Egress/integrity assertions must be **blocking on the box producing published numbers** (fail, not
  silently skip); keep a thin hermetic guard variant so CI without Docker still tests scrub/cap/timeout
  (lens 2, 5). Pin base image by digest; stamp image ID (lens 5).
- Frame "compute held constant (REV 4.3)" precisely: web run_python = compute+retrieval, ours =
  compute-only — the INTENDED data-access axis; state it in the pre-reg so it's not read as a confound
  (lens 3). Under A only: short connect-timeouts in tests (DROP makes blocked connects hang to timeout
  — lens 2); bind published DB port to `127.0.0.1` + drop ALL gateway A/AAAA records + verify the
  gateway-is-private assumption at runtime (lens 1); no `-e` host env into the container; forbid
  `docker.sock`/`--privileged`/`--pid=host`/`--network=host` via an argv check (lens 1).
- Phase merge (lens 4): egress rules + their proving assertions must land together (never ship an
  unproven integrity control as a checkpoint) -> Phase 1 (container backend + guard parity +
  fail-closed, STOP) / Phase 2 (egress + injection + assertions + security-sentinel, STOP) / re-pilot.

## Security-sentinel review (Phase 2 gate, 2026-06-29) — findings + dispositions
Reviewed the egress/gold-leak boundary statically against the threat model. Affirmed correct: the
no-gold-leak guard (`_build_sandbox_inputs` structurally cannot receive `gold`/`params`), `run_python`
`--network none` isolation, the `_sandbox_argv` lockdown (forbidden-flags test genuinely proves it),
container reaping, redirect re-guarding, and the ours/web disallow-list parity. Findings:
- **M2 — IPv4-mapped IPv6 / unspecified gap (FIXED).** `::ffff:127.0.0.1` / `0.0.0.0` could pass the
  guard on Python 3.12.0–3.12.3 (mapped-address property delegation landed in 3.12.4). `_is_safe_public_url`
  now unwraps `ipv4_mapped` + rejects `is_unspecified`; four regression URLs added to the BLOCKED set.
- **M3 — `ANTHROPIC_API_KEY` env-pop concurrency (DOCUMENTED).** Process-global pop/restore is safe
  because the solver runs instances SEQUENTIALLY on one `asyncio.Runner`; annotated with the invariant
  + the fix (per-query `env=`) required IF the matrix is ever made in-process-concurrent.
- **L2 — orphaned `docker run` client on timeout (FIXED).** Added `_kill_proc(proc)` on the
  CancelledError/TimeoutError paths (the container was already reaped by name; this kills the client).
- **L3 — injected-filename traversal defense-in-depth (FIXED).** `_exec_sandboxed_python` now skips any
  key where `Path(fname).name != fname` before the host write (today's keys are already safe).
- **L4 — secret-redaction breadth (FIXED).** `_safe_err` now also scrubs `Bearer <token>`.
- **M1 — SSRF guard TOCTOU / time-based DNS rebind (ACCEPTED RESIDUAL, documented in-code + here).**
  The validated resolution isn't pinned to httpx's connect, so a host that is public at check-time and
  loopback at connect-time isn't stopped. Practical exploitability is near-zero in THIS gate: the URL
  consumer is an honest model answering vote questions (not an adversary registering a rebinding
  domain), our private surface is loopback-only, and `:5432` doesn't speak HTTP (only `:8000` is a
  meaningful HTTP target). The robust fix (pin the connect to a vetted IP) breaks HTTPS SNI/cert
  validation against the real public hosts the web arm must reach, so it's deferred; the guard
  docstring warns against unmodified reuse where URLs are attacker-controlled. Phase-3's deferred
  cred-rotation is the further belt-and-suspenders. Does NOT block the gate under this threat model.

### Affirmed (don't re-litigate)
Frozen `grading_contract_hash`/`content_hash` untouched (`solvers.py`/`lift_instances.py` outside both
hashes — confirmed); symmetric RO observation mount is fair like-for-like; `--network none` removes
egress (verified); Windows path bind-mounts work from `create_subprocess_exec` (the Git-Bash
path-mangling is NOT in the code path — use `Path(d).as_posix()` defensively); container start latency
~0.28s (none) / ~0.45s (bridge) — plan estimate holds; `requires_pg`-style skip mechanics are sound.

## Sources & References
- Scope: `docs/scopes/2026-06-29-run-python-egress-isolation-scope.md`. Design + pilot evidence:
  [[project_condorcet_experimental_design]] (REV 4.3, the urllib->voteview finding).
- Code: `lab/solvers.py` `_exec_sandboxed_python` (L644), `_make_run_python_tool` (L684),
  `_is_safe_public_url` (L555, the deny-range precedent), `_sdk_tool_config` (L833, ours/web branch).
  `tests/test_lab/test_sandbox_exec.py` (port to requires_docker). `docker-compose.yml`
  (`pgvector/pgvector:pg16`, `5432:5432` -> the host PG to wall off). Apparatus: PR #51 (`main`
  @ `8eed6b4`).
