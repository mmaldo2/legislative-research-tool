# Preserved LegalLM student candidate artifacts

This directory keeps compact, reviewable artifacts for the current LegalLM student candidate without committing bulky LoRA adapter/checkpoint files.

## Current candidate leader

- Candidate: `qwen3_4b_2507_pi4_apa3_seed23`
- Model: `Qwen/Qwen3-4B-Instruct-2507`
- Dataset: `legal_lm/data/student_pilot/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3`
- Local adapter, preserved on disk but ignored from git: `legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/qwen3_4b_2507_lora_seed23/adapter`

## Why this candidate is preserved

- Closed-label accuracy: 18/18
- Rule guardrails: pass
- Rule meta-rubric reasoning: 0/6
- Manual rule score: 11.75/12
- It beats the original Qwen3 leader, which had 18/18 closed-label accuracy but 6/6 meta-rubric rule reasoning rows.

See `qwen3_4b_2507_pi4_apa3_seed23/autoresearch_summary.md` and `qwen3_4b_2507_pi4_apa3_seed23/artifact_manifest.json` for details.
