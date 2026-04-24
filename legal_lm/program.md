# legal_lm autoresearch

This is a Karpathy-style autoresearch loop for legal teacher distillation.

## Setup

To start a run, work with the user to:

1. Agree on a run tag and use a fresh working branch if desired.
2. Read the in-scope files:
   - `legal_lm/program.md` — this file, the research-org instructions.
   - `legal_lm/teacher_loop.py` — the only mutable experiment surface.
   - `legal_lm/eval/teacher_batch_audit.py` — fixed batch audit harness. Do not modify during a run unless the human explicitly changes scope.
   - `legal_lm/schemas/teacher_example.schema.json` — fixed schema.
   - `legal_lm/schemas/preference_example.schema.json` — fixed schema.
   - `legal_lm/schemas/source_example.schema.json` — fixed curated-source schema.
   - `legal_lm/data/sources/*.jsonl` — curated source corpora used for batch generation, currently including `rule_reasoning`, `definition_classification`, `policy_regulatory_qa`, and `sara_entailment`.
3. Initialize the results log with:
   - `python -m legal_lm.teacher_loop init-results legal_lm/results/teacher_runs/results.tsv`
4. Confirm setup looks good, then begin autonomous experimentation.

## Scope

### What you CAN do
- Modify `legal_lm/teacher_loop.py`
- Generate new teacher batches as JSONL
- Audit and score batches
- Log keep/discard decisions
- Experiment with batch-policy knobs:
  - doctrine weighting
  - family balancing
  - confidence defaults
  - rubric variants
  - seed/subsampling strategies
- Run smoke evals so downstream performance can override pure batch quality
- Summarize checkpoints for the human only periodically

### What you CANNOT do by default
- Train on benchmark test rows
- Modify the contamination policy by stealth
- Ask the human to approve every example
- Change multiple files at once without a clear reason

## Goal

Get the highest downstream-quality teacher batches while preserving contamination safety and stylistic consistency.

Primary cheap metric:
- `teacher_batch_score` from the audit harness

Secondary metric:
- downstream student improvement on held-out legal benchmark slices
- minimal smoke-eval accuracy when `audit-batch` is run with `--smoke-eval-path`
- smoke-eval rows should be semantically held out rather than paraphrase-near copies of curated source prompts

## Loop

1. Modify `legal_lm/teacher_loop.py` with one experimental idea.
2. Generate a candidate batch from curated source rows, e.g. `python -m legal_lm.teacher_loop generate-batch <source.jsonl> <batch.jsonl> --batch-size N --seed S`.
3. Adjust policy knobs when useful:
   - `--family-balancing equal`
   - `--doctrine-weights-json '{...}'`
   - `--confidence-by-family-json '{...}'`
   - `--rubric-variant checklist|concise|verbatim`
   - `--sampling-strategy random|head`
   - `--subsample-ratio R`
4. Run the audit/scoring step, optionally with smoke eval:
   - `python -m legal_lm.teacher_loop audit-batch <batch.jsonl> <results.tsv> <run_id> <batch_id> <description> --smoke-eval-path <eval.jsonl>`
5. Log the result to `legal_lm/results/teacher_runs/results.tsv`.
6. Keep only batches that improve the best score and satisfy fixed constraints.
7. Continue until interrupted.

## Reporting cadence

Do NOT report every example.

Report only at:
- setup complete
- first kept batch
- every 3-5 kept batches
- any escalation or contamination ambiguity

## Constraints

- Favor simpler policies when scores are similar.
- Any test-split leakage is an automatic discard.
- If a batch crashes the loop or creates malformed rows, fix or discard it and move on.
