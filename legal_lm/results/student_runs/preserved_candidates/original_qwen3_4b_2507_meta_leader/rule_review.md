# Rule reasoning review

## rule-eval-001
- Doctrine: Evidence
- Prompt: Under Rule 403, when may a court keep out relevant evidence?
- Reference answer: A court may exclude relevant evidence if its probative value is substantially outweighed by dangers such as unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or needlessly presenting cumulative evidence.
- Reference reasoning: A correct answer should identify the substantial-outweighing standard and the main Rule 403 dangers.
- Rubric points:
  - States the substantial-outweighing standard
  - Mentions the principal Rule 403 dangers
- Base output:
```text
Answer: A court may exclude relevant evidence under Rule 403 if its probative value is substantially outweighed by the risk of unfair prejudice, confusion of the issues, or misleading the jury.

Reasoning: Rule 403 of the Federal Rules of Evidence allows a court to exclude relevant evidence when its admission would create undue prejudice, confuse the issues, or mislead the jury, even if the evidence is otherwise relevant. The decision must be based on a balancing test between relevance and potential harm to the trial's fairness.
```
- Base parsed answer: A court may exclude relevant evidence under Rule 403 if its probative value is substantially outweighed by the risk of unfair prejudice, confusion of the issues, or misleading the jury.
- Fine-tuned output:
```text
Answer: A court may exclude relevant evidence if its probative value is substantially outweighed by dangers such as unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or needlessly presenting cumulative evidence.
Reasoning: The answer should quote the specific Rule 403 exception and keep reasoning concise and legally grounded.
```
- Fine-tuned parsed answer: A court may exclude relevant evidence if its probative value is substantially outweighed by dangers such as unfair prejudice, confusing the issues, misleading the jury, undue delay, wasting time, or needlessly presenting cumulative evidence.

## rule-eval-002
- Doctrine: Civil Procedure
- Prompt: What showing is needed for a preliminary injunction in federal court?
- Reference answer: A plaintiff generally must show a likelihood of success on the merits, a likelihood of irreparable harm without preliminary relief, that the balance of equities favors relief, and that an injunction is in the public interest.
- Reference reasoning: A complete answer should identify the four familiar preliminary-injunction factors.
- Rubric points:
  - Lists the core preliminary-injunction factors
  - Includes irreparable harm and likelihood of success
- Base output:
```text
Answer: A showing of both irreparable injury and a likelihood of success on the merits.
Reasoning: Under the standard established in *Perry v. United States*, a plaintiff must demonstrate that they will suffer irreparable harm absent a preliminary injunction and that there is a substantial probability that they will succeed on the merits of their claim. This ensures that the injunction is granted only when necessary and justified by the balance of equities.
```
- Base parsed answer: A showing of both irreparable injury and a likelihood of success on the merits.
- Fine-tuned output:
```text
Answer: A preliminary injunction is generally granted when a party shows a likelihood of success on the merits, a likelihood of irreparable harm, and a balance of equities favoring the moving party.
Reasoning: The answer should identify the three traditional preliminary injunction factors.
```
- Fine-tuned parsed answer: A preliminary injunction is generally granted when a party shows a likelihood of success on the merits, a likelihood of irreparable harm, and a balance of equities favoring the moving party.

## rule-eval-003
- Doctrine: Constitutional Law
- Prompt: Under strict scrutiny, what must the government show?
- Reference answer: To satisfy strict scrutiny, the government generally must show that the challenged law or action serves a compelling governmental interest and is narrowly tailored to achieve that interest using the least restrictive means or an equally exacting fit.
- Reference reasoning: A correct answer should state both the compelling-interest and narrow-tailoring requirements.
- Rubric points:
  - States the compelling-interest requirement
  - States the narrow-tailoring requirement
- Base output:
```text
Answer: Under strict scrutiny, the government must show that the law is substantially related to an important governmental interest and is the least restrictive means of achieving that interest.
Reasoning: Strict scrutiny is the highest level of judicial review applied to laws that significantly affect fundamental rights or involve suspect classifications. The government must meet a high burden by demonstrating both the importance of the interest and the minimal impact on individual rights.
```
- Base parsed answer: Under strict scrutiny, the government must show that the law is substantially related to an important governmental interest and is the least restrictive means of achieving that interest.
- Fine-tuned output:
```text
Answer: Under strict scrutiny, the government must show that the challenged law serves a compelling governmental interest and is narrowly tailored to achieve that interest.
Reasoning: The answer should identify both the compelling interest requirement and the narrowly tailored requirement.
```
- Fine-tuned parsed answer: Under strict scrutiny, the government must show that the challenged law serves a compelling governmental interest and is narrowly tailored to achieve that interest.

## rule-eval-004
- Doctrine: Administrative Law
- Prompt: Under the APA, what notice-and-comment steps are generally required for legislative rules?
- Reference answer: For legislative rules, the Administrative Procedure Act generally requires an agency to publish notice of proposed rulemaking, give interested persons an opportunity to comment, and then issue a final rule with a concise general statement of basis and purpose, subject to certain exceptions.
- Reference reasoning: A complete answer should name notice, an opportunity to comment, and issuance of a final rule with a basis-and-purpose statement.
- Rubric points:
  - States the notice-and-comment core steps accurately
  - Makes clear the rule concerns legislative rules
- Base output:
```text
Answer: Under the Administrative Procedure Act (APA), legislative rules generally require notice and comment procedures, including publication of a proposed rule in the Federal Register, providing an opportunity for public comment, and considering those comments before finalizing the rule.

Reasoning: The APA mandates that agencies follow notice-and-comment procedures for most rules to ensure transparency, public participation, and judicial review, as outlined in 5 U.S.C. § 553. This applies to legislative rules, which are rules adopted by a legislative body or agency under its authority.
```
- Base parsed answer: Under the Administrative Procedure Act (APA), legislative rules generally require notice and comment procedures, including publication of a proposed rule in the Federal Register, providing an opportunity for public comment, and considering those comments before finalizing the rule.
- Fine-tuned output:
```text
Answer: Under the APA, notice-and-comment rulemaking generally requires a notice of proposed rulemaking, a comment period, and a final rule published in the Federal Register.
Reasoning: The answer should identify the three standard notice-and-comment steps required by the APA for legislative rules.
```
- Fine-tuned parsed answer: Under the APA, notice-and-comment rulemaking generally requires a notice of proposed rulemaking, a comment period, and a final rule published in the Federal Register.

## rule-eval-005
- Doctrine: Contracts
- Prompt: What does contract law mean by consideration?
- Reference answer: Consideration is a bargained-for exchange in which each party gives or promises something of legal value in return for the other's promise or performance.
- Reference reasoning: A complete answer should identify a bargain and legal value on both sides.
- Rubric points:
  - States the bargained-for exchange concept
  - Mentions legal value on both sides
- Base output:
```text
Answer: Consideration in contract law means something of value that is exchanged between parties, demonstrating mutual agreement and intent to be bound.

Reasoning: It is a fundamental element of a valid contract, ensuring that neither party is bound by a promise without giving something in return, thus preventing gratuitous or one-sided agreements.
```
- Base parsed answer: Consideration in contract law means something of value that is exchanged between parties, demonstrating mutual agreement and intent to be bound.
- Fine-tuned output:
```text
Answer: Consideration is a bargained-for exchange of value between the parties.
Reasoning: A legal answer should identify the bargained-for exchange of value between the parties.
```
- Fine-tuned parsed answer: Consideration is a bargained-for exchange of value between the parties.

## rule-eval-006
- Doctrine: Contracts
- Prompt: In contract law, what does the parol evidence rule generally bar?
- Reference answer: The parol evidence rule generally bars the use of prior or contemporaneous extrinsic agreements to vary or contradict the terms of a final written agreement, subject to recognized exceptions.
- Reference reasoning: A correct answer should focus on prior or contemporaneous extrinsic terms that would vary or contradict a final writing.
- Rubric points:
  - States the final-written-agreement premise
  - States the bar on varying or contradicting with prior or contemporaneous terms
- Base output:
```text
Answer: The parol evidence rule generally bars the introduction of oral or written statements made before or after a written contract to contradict, modify, or add to the terms of the written agreement.
Reasoning: The rule applies to prevent inconsistent prior or subsequent statements from undermining the finality and clarity of a written contract, assuming the contract was fully integrated and executed with mutual assent.
```
- Base parsed answer: The parol evidence rule generally bars the introduction of oral or written statements made before or after a written contract to contradict, modify, or add to the terms of the written agreement.
- Fine-tuned output:
```text
Answer: The parol evidence rule generally bars the introduction of prior or contemporaneous agreements to vary or contradict a final written integrated contract.
Reasoning: The answer should identify the rule's general effect and scope.
```
- Fine-tuned parsed answer: The parol evidence rule generally bars the introduction of prior or contemporaneous agreements to vary or contradict a final written integrated contract.
