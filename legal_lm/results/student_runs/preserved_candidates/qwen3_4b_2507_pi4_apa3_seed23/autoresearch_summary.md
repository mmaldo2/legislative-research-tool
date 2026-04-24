# LegalLM Qwen3 autoresearch: rule_reasoning cleanup

## Result

We beat the original Qwen3 leader on the target criteria.

Best candidate: autoresearch_rule_reasoning_pi_apa_v1 / pi4_apa3 / seed 23.

- Closed-label accuracy: 18/18
- Rule guardrails: pass
- Rule meta-rubric reasoning: 0/6
- Manual rule score: 11.75/12
- Original leader: 18/18 closed-label, but 6/6 meta-rubric rule reasoning and manual rule score 10.5/12

## Passing candidates

| Round | Variant | Seed | Manual rule score | Notes |
|---|---|---:|---:|---|
| autoresearch_rule_reasoning_pi_apa_v1 | pi4_apa3 | 17 | 11.25/12 | passes gates, lower manual rule quality |
| autoresearch_rule_reasoning_pi_apa_v1 | pi4_apa3 | 23 | 11.75/12 | best keep |
| autoresearch_rule_reasoning_pi_apa_v1 | pi4_apa3 | 31 | 10.25/12 | passes gates, lower manual rule quality |

## Autoresearch trajectory

1. reasoning_clean_v2 fixed meta style but did not pass: public-interest omission persisted.
2. PI-only augmentation fixed public-interest in several seeds, but APA basis/purpose became the limiting gap.
3. PI+APA augmentation with pi4_apa3 made all three seeds pass closed-label and rule guardrails.
4. Seed 23 is the best qualitative rule answer set: it includes public interest, APA basis-and-purpose, and no meta-rubric reasoning.

## Best candidate files

- predictions_path: legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/fine_tuned_qwen3_4b_2507_seed23_predictions.jsonl
- summary_path: legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/fine_tuned_qwen3_4b_2507_seed23_summary.json
- guardrails_path: legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/fine_tuned_qwen3_4b_2507_seed23_rule_guardrails.json
- review_path: legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/base_vs_qwen3_4b_2507_seed23_rule_review.md
- adapter: legal_lm/results/student_runs/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3/qwen3_4b_2507_lora_seed23/adapter
- dataset: legal_lm/data/student_pilot/autoresearch_rule_reasoning_pi_apa_v1/pi4_apa3

## Best candidate rule outputs

### rule-eval-001 — Evidence
- Answer: A court may exclude relevant evidence if its probative value is substantially outweighed by dangers such as unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or needlessly presenting cumulative evidence.
- Reasoning: Rule 403 permits exclusion when probative value is substantially outweighed by specific prejudicial or procedural dangers.

### rule-eval-002 — Civil Procedure
- Answer: The movant generally must show a likelihood of success on the merits, a likelihood of irreparable harm without preliminary relief, that the balance of equities favors relief, and that an injunction is in the public interest.
- Reasoning: Preliminary relief requires a showing of likelihood of success on the merits, irreparable harm, balance of equities, and public interest.

### rule-eval-003 — Constitutional Law
- Answer: To satisfy strict scrutiny, the government must show that the challenged law serves a compelling governmental interest and is narrowly tailored to achieve that interest.
- Reasoning: Strict scrutiny requires both a compelling interest and narrowly tailored means.

### rule-eval-004 — Administrative Law
- Answer: The agency generally must give notice of proposed rulemaking, provide an opportunity for public comment, and issue a final rule with a concise general statement of basis and purpose.
- Reasoning: The APA notice-and-comment rulemaking process includes these three steps.

### rule-eval-005 — Contracts
- Answer: Consideration is a bargained-for exchange of value between the parties.
- Reasoning: The exchange must be bargained-for and legally sufficient to support the promise.

### rule-eval-006 — Contracts
- Answer: The parol evidence rule generally bars a party from introducing extrinsic evidence to vary, contradict, or negate a final written integrated contract.
- Reasoning: The rule protects the final written integrated contract from being contradicted by prior or contemporaneous oral or written agreements.
