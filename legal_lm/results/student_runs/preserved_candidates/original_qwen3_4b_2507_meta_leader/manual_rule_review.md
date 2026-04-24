# Qwen3 4B rule_reasoning manual rubric pass

Reviewed at: 2026-04-23T19:36:21-04:00

## Summary

- Base answer-line score: 6.25/12.0 (mean 1.042/2)
- Fine-tuned answer-line score: 10.5/12.0 (mean 1.75/2)
- Answer-line delta: +4.25/12.0
- Base meta-rubric reasoning rows: 0/6
- Fine-tuned meta-rubric reasoning rows: 6/6

Bottom line: Qwen3 fine-tuning materially improves the rule answers, but the rule_reasoning target style is not clean enough to bless. The answer lines are mostly good; the reasoning lines are often rubric-meta text copied from the training target style.

## Remaining gaps

- rule-eval-002: preliminary-injunction answer omits public interest and says three factors.
- rule-eval-004: APA answer omits final rule concise general statement of basis and purpose.
- rule-eval-005: consideration answer should explicitly mention legal value on both sides.
- fine-tuned rule_reasoning reasoning lines are meta-rubric in all 6 rows.

## Root-cause evidence

- student_pilot_train_rule_reasoning_rows: 10
- student_pilot_train_meta_style_reasoning_rows: 9
- student_pilot_dev_rule_reasoning_rows: 2
- student_pilot_dev_meta_style_reasoning_rows: 2
- fine_tuned_rule_reasoning_meta_style_generated_rows: 6
- interpretation: The model learned the meta-rubric reasoning style from rule_reasoning teacher_reasoning_short targets.

## Row-level scores

### rule-eval-001 — Evidence

- Prompt: Under Rule 403, when may a court keep out relevant evidence?
- Rubric points: States the substantial-outweighing standard; Mentions the principal Rule 403 dangers
- Base score: 1.5/2
  - Parsed answer: A court may exclude relevant evidence under Rule 403 if its probative value is substantially outweighed by the risk of unfair prejudice, confusion of the issues, or misleading the jury.
  - Finding: Correct substantial-outweighing standard and several central dangers; narrower than reference because it omits undue delay, wasting time, and cumulative evidence.
  - Meta-style reasoning: false
- Fine-tuned score: 2.0/2
  - Parsed answer: A court may exclude relevant evidence if its probative value is substantially outweighed by dangers such as unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or needlessly presenting cumulative evidence.
  - Finding: Answer matches the reference rule and includes the main listed Rule 403 dangers.
  - Meta-style reasoning: true
- Remaining issue: Fine-tuned reasoning is meta-rubric text rather than an explanation.

### rule-eval-002 — Civil Procedure

- Prompt: What showing is needed for a preliminary injunction in federal court?
- Rubric points: Lists the core preliminary-injunction factors; Includes irreparable harm and likelihood of success
- Base score: 1.0/2
  - Parsed answer: A showing of both irreparable injury and a likelihood of success on the merits.
  - Finding: Names likelihood of success and irreparable injury but omits equities and public interest.
  - Meta-style reasoning: false
- Fine-tuned score: 1.5/2
  - Parsed answer: A preliminary injunction is generally granted when a party shows a likelihood of success on the merits, a likelihood of irreparable harm, and a balance of equities favoring the moving party.
  - Finding: Adds balance of equities but still omits the public-interest factor and incorrectly describes the standard as three factors.
  - Meta-style reasoning: true
- Remaining issue: Needs public interest and should not call the test three-factor.

### rule-eval-003 — Constitutional Law

- Prompt: Under strict scrutiny, what must the government show?
- Rubric points: States the compelling-interest requirement; States the narrow-tailoring requirement
- Base score: 0.5/2
  - Parsed answer: Under strict scrutiny, the government must show that the law is substantially related to an important governmental interest and is the least restrictive means of achieving that interest.
  - Finding: Confuses strict scrutiny with intermediate scrutiny by using substantially related / important interest, though it mentions least restrictive means.
  - Meta-style reasoning: false
- Fine-tuned score: 2.0/2
  - Parsed answer: Under strict scrutiny, the government must show that the challenged law serves a compelling governmental interest and is narrowly tailored to achieve that interest.
  - Finding: Correctly states compelling governmental interest and narrow tailoring.
  - Meta-style reasoning: true
- Remaining issue: Fine-tuned answer is good; reasoning remains meta-rubric.

### rule-eval-004 — Administrative Law

- Prompt: Under the APA, what notice-and-comment steps are generally required for legislative rules?
- Rubric points: States the notice-and-comment core steps accurately; Makes clear the rule concerns legislative rules
- Base score: 1.5/2
  - Parsed answer: Under the Administrative Procedure Act (APA), legislative rules generally require notice and comment procedures, including publication of a proposed rule in the Federal Register, providing an opportunity for public comment, and considering those comments before finalizing the rule.
  - Finding: Correctly names notice, public comment, and consideration/finalization, and keeps the legislative-rule frame, but omits the concise basis-and-purpose statement.
  - Meta-style reasoning: false
- Fine-tuned score: 1.5/2
  - Parsed answer: Under the APA, notice-and-comment rulemaking generally requires a notice of proposed rulemaking, a comment period, and a final rule published in the Federal Register.
  - Finding: Names NPRM, comment period, and final rule, but also omits the concise basis-and-purpose statement.
  - Meta-style reasoning: true
- Remaining issue: Needs basis-and-purpose statement in the answer line.

### rule-eval-005 — Contracts

- Prompt: What does contract law mean by consideration?
- Rubric points: States the bargained-for exchange concept; Mentions legal value on both sides
- Base score: 1.0/2
  - Parsed answer: Consideration in contract law means something of value that is exchanged between parties, demonstrating mutual agreement and intent to be bound.
  - Finding: Recognizes exchange of value but does not state the bargained-for requirement clearly.
  - Meta-style reasoning: false
- Fine-tuned score: 1.5/2
  - Parsed answer: Consideration is a bargained-for exchange of value between the parties.
  - Finding: States bargained-for exchange of value; could be stronger by saying each party gives or promises legal value.
  - Meta-style reasoning: true
- Remaining issue: Needs explicit legal value on both sides for a fully complete answer.

### rule-eval-006 — Contracts

- Prompt: In contract law, what does the parol evidence rule generally bar?
- Rubric points: States the final-written-agreement premise; States the bar on varying or contradicting with prior or contemporaneous terms
- Base score: 0.75/2
  - Parsed answer: The parol evidence rule generally bars the introduction of oral or written statements made before or after a written contract to contradict, modify, or add to the terms of the written agreement.
  - Finding: Correct general direction but incorrectly includes later statements and does not clearly anchor the bar to prior/contemporaneous agreements and a final integrated writing.
  - Meta-style reasoning: false
- Fine-tuned score: 2.0/2
  - Parsed answer: The parol evidence rule generally bars the introduction of prior or contemporaneous agreements to vary or contradict a final written integrated contract.
  - Finding: Correctly states prior or contemporaneous agreements, variation/contradiction, and final written integrated contract.
  - Meta-style reasoning: true
- Remaining issue: Fine-tuned answer is strong; reasoning remains meta-rubric.

## Recommendation

Do not bless rule_reasoning as final yet. Keep Qwen3 as the leading student candidate, but create a cleaned rule-reasoning-target v2 and retrain/rerun before calling open-ended answers healthy.
