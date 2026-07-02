"""The run manifest -- the ONE schema shared by the matrix driver (writer) and lift_analysis (read).

A matrix run (ablation.run_matrix) writes `RUNS_DIR/manifest_<run_id>.json` so the analysis knows
EXACTLY which per-cell trace files belong to the run (deterministic provenance, not a fragile
timestamp glob over a dir that already holds dozens of files). It is written CRASH-SAFE: the param
block + the pinned hashes + the pre-registration doc SHA are persisted at run START, and each cell
file path is appended (and re-persisted) as that cell completes -- so a late failure in a long,
expensive sequential run still leaves an analyzable partial manifest.

Modeled with Pydantic (like TraceRecord/RunContext in trace.py) so writer and reader reference ONE
definition, not a hand-rolled dict on each side. NON-FROZEN: this file is in NEITHER frozen hash.
"""

import json
from pathlib import Path

from pydantic import BaseModel


class RunManifest(BaseModel):
    run_id: str
    params: dict  # {models, surfaces, templates, n, repeats, caps...} -- the run's pinned knobs
    rollout_seed: int  # ablation's --seed (instance sampling); the bootstrap seed lives in the
    # analysis artifact, NOT here (it is chosen at analysis time, not run time).
    prereg_doc_sha: str | None = None  # the committed pre-registration doc blob/commit SHA (anchor)
    # Stamped from the RunContext once prepare_run runs (before this run's first cell); None until
    # then so the manifest can be created + persisted at the very start (crash-safe param block).
    grading_contract_hash: str | None = None
    content_hash: str | None = None
    dataset_fingerprint: dict = {}
    cell_files: list[str] = []  # per-cell jsonl filenames (basenames; resolved against RUNS_DIR)

    def stamp_hashes(self, ctx, runs_dir: Path) -> None:
        """Record the run's contract/content hashes + dataset fingerprint from the RunContext and
        persist. Idempotent (re-stamping with the same ctx is a no-op write)."""
        self.grading_contract_hash = ctx.grading_contract_hash
        self.content_hash = ctx.content_hash
        self.dataset_fingerprint = dict(ctx.dataset_fingerprint)
        self.save(runs_dir)

    @staticmethod
    def path_for(run_id: str, runs_dir: Path) -> Path:
        return runs_dir / f"manifest_{run_id}.json"

    def save(self, runs_dir: Path) -> None:
        """Persist (idempotent). Called at start and after each appended cell file."""
        runs_dir.mkdir(parents=True, exist_ok=True)
        self.path_for(self.run_id, runs_dir).write_text(self.model_dump_json(indent=2) + "\n")

    def add_cell(self, cell_path: Path, runs_dir: Path) -> None:
        """Append a completed cell's filename and re-persist (crash-safe incremental write)."""
        self.cell_files.append(cell_path.name)
        self.save(runs_dir)

    @classmethod
    def load(cls, run_id: str, runs_dir: Path) -> "RunManifest":
        path = cls.path_for(run_id, runs_dir)
        if not path.exists():
            raise FileNotFoundError(
                f"no manifest for run_id={run_id!r} at {path} -- wrong run-id, or the run never "
                f"wrote a manifest (pre-manifest ablation files are not analyzable by run-id)"
            )
        return cls.model_validate(json.loads(path.read_text()))
