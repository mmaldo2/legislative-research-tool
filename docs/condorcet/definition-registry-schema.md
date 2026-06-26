# Definition Registry — Schema & v1 Seed

> **What this is.** The versioned store of **frozen operational definitions** the cross-pressure computations depend on. It **formalizes the config the statehouse-intel spec already isolates** (`statehouse-intel-repo-spec.md` §10: CPI weights, classification thresholds, vote-inclusion rules, the issue taxonomy) and adds versioning + freeze + a grading contract + a dependency DAG. It adopts that spec's vocabulary as canonical: **`position_gap`, `salience_w`, `vulnerability`, `perception_gap`, `cross_pressure_index` (CPI), and `target_class`** ∈ {information_target, pressure_target, low_leverage, aligned}. Computations run over **System 2's DuckDB marts** (per the ecosystem map).
>
> It is the **seam** between the two benchmark layers:
> - **Factual layer** *consumes* a frozen definition by version → the computation is deterministic → a Family 8 task becomes `C-def` (code-gradable) instead of `→M`.
> - **Methodological layer** *produces and justifies* each definition → experts bless the contested parameters.
>
> **Hard rule:** a frozen definition is **immutable**. Changing it means publishing a new version; both versions coexist; every task, trace, and output cites the version it used. No cross-pressure computation may use an inline threshold, weight, or mapping — it must reference a registry entry by `id@version`.
>
> **Audience:** coding agents and engineers. Placeholder values below are marked `# PLACEHOLDER` and must be set + reviewed before freeze (see §8).

---

## 1. Entry schema

### 1.1 YAML shape (the canonical on-disk form)

```yaml
id: cross_pressure_index           # stable slug, unique
version: "1.0.0"                   # semver; bump on any change
status: draft                      # draft | active | deprecated | superseded
frozen: false                      # true => immutable
frozen_at: null                    # ISO datetime when frozen
supersedes: null                   # "id@version" or null
superseded_by: null

output_type: score                 # scalar | boolean | score | categorical | set | mapping
unit_scale: "[0,1], higher = more cross-pressured"   # how to read the output
definition_kind: formula           # constant | formula | mapping_table | derivation | set_rule
sensitive_data: false              # true => touches the segregated sensitive-data root

inputs:                            # every field read, with its source + run-binding
  - name: position_gap
    source: registry               # registry | structured_core | ideal_point_store | mrp_store | district_profile | survey_root
    ref: "position_gap@1.0.0"
    run_bound: true
  - name: vulnerability
    source: registry
    ref: "vulnerability@1.0.0"
    run_bound: false

depends_on:                        # other registry defs (builds the DAG)
  - "position_gap@1.0.0"
  - "salience_w@1.0.0"
  - "vulnerability@1.0.0"
  - "perception_gap@1.0.0"

run_bindings:                      # which estimation runs this is pinned to (null if n/a)
  ideal_point_run: "shor_mccarty_la_2026_03"
  mrp_run: "la_issues_2026_03"
  survey_wave: null

spec: |                            # the exact computation. MUST be unambiguous.
  CPI = clamp01( w_pos*abs(position_gap_norm) + w_sal*salience_w
               + w_vuln*vulnerability + w_perc*perception_gap_norm )
  # weights in config (sum to 1); perception_gap term drops to 0 when unpolled.

reference_impl:                    # canonical code + a deterministic test vector
  path: "registry/impl/cross_pressure_index_v1.py"
  test_vector: "registry/tests/cross_pressure_index_v1.json"

# ---- methodological face (justification; graded/blessed by experts) ----
rationale: |
  The composite that joins the engines: how far a member's position sits from
  the district (position_gap), how much the district cares (salience_w), how
  electorally exposed the member is (vulnerability), and how wrong they are
  about their district (perception_gap). Weighted combination per §10 of the
  statehouse-intel spec.
provenance:
  - "statehouse-intel-repo-spec.md §10 (cross-pressure module)"
  - "Broockman & Skovron (2018) APSR — misperception of constituency opinion"
contested_parameters:
  - param: "weights (w_pos, w_sal, w_vuln, w_perc)"
    current_value: "equal  # PLACEHOLDER"
    plausible_alternatives: ["position-dominant", "vulnerability-dominant"]
    why_contested: "the weighting is the core editorial choice; sensitivity analysis in the report appendix"
sensitivity: "registry/sensitivity/cross_pressure_index_v1.md"
reviewers: []                      # who blessed this (academic/domain partners)

# ---- grading contract (how the factual layer uses it) ----
cleanliness_contract:
  tier: C-def
  grader: score_within_tol         # exact | set_match | score_within_tol
  tolerance: 0.001                 # required if grader == score_within_tol
  gold_source: reference_impl      # gold answer = reference_impl run under THIS frozen version
  citation_required: true          # agent answer must name id@version used
notes: ""
```

### 1.2 Pydantic model (the in-code form; stack is Python)

```python
from enum import Enum
from datetime import datetime
from pydantic import BaseModel

class OutputType(str, Enum):
    scalar = "scalar"; boolean = "boolean"; score = "score"
    categorical = "categorical"; set_ = "set"; mapping = "mapping"

class DefKind(str, Enum):
    constant = "constant"; formula = "formula"; mapping_table = "mapping_table"
    derivation = "derivation"; set_rule = "set_rule"

class Status(str, Enum):
    draft = "draft"; active = "active"; deprecated = "deprecated"; superseded = "superseded"

class Grader(str, Enum):
    exact = "exact"; set_match = "set_match"; score_within_tol = "score_within_tol"

class Input(BaseModel):
    name: str
    source: str                       # registry | structured_core | ideal_point_store | mrp_store | district_profile | survey_root
    ref: str                          # column/key or "id@version"
    run_bound: bool = False

class ContestedParam(BaseModel):
    param: str
    current_value: str
    plausible_alternatives: list[str] = []
    why_contested: str

class CleanlinessContract(BaseModel):
    tier: str = "C-def"
    grader: Grader
    tolerance: float | None = None
    gold_source: str = "reference_impl"
    citation_required: bool = True

class RunBindings(BaseModel):
    ideal_point_run: str | None = None
    mrp_run: str | None = None
    survey_wave: str | None = None

class Definition(BaseModel):
    id: str
    version: str
    status: Status = Status.draft
    frozen: bool = False
    frozen_at: datetime | None = None
    supersedes: str | None = None
    superseded_by: str | None = None
    output_type: OutputType
    unit_scale: str
    definition_kind: DefKind
    sensitive_data: bool = False
    inputs: list[Input]
    depends_on: list[str] = []
    run_bindings: RunBindings = RunBindings()
    spec: str
    reference_impl: dict                # {path, test_vector}
    rationale: str
    provenance: list[str] = []
    contested_parameters: list[ContestedParam] = []
    sensitivity: str | None = None
    reviewers: list[str] = []
    cleanliness_contract: CleanlinessContract
    notes: str = ""
```

---

## 2. Governance & lifecycle (hard rules)

1. **Immutability.** Once `frozen: true`, the entry never changes. Any change = new `version`, new entry, `supersedes` set, old entry `status: superseded` but **retained forever** (old tasks/traces still reference it).
2. **Freeze gate.** An entry may be frozen only when: all `contested_parameters` have a set value, `reference_impl` + `test_vector` exist and pass, and at least one reviewer has blessed it. (See §8 checklist.)
3. **Citation.** Every cross-pressure computation, benchmark task, and trace records the `id@version` of every definition it used. No inline thresholds/weights/mappings — ever.
4. **Run pinning.** A definition bound to estimates (`run_bound: true`) is meaningless without its `run_bindings`. The (definition version + run set) together define the gold answer.
5. **Composition.** A definition that `depends_on` others inherits their frozen status — you cannot freeze `target_class@1.0.0` until everything it depends on is frozen.
6. **Versioning across the registry.** A "registry release" is a named, frozen set (e.g., `LA-v1`) pinning a coherent version of every entry + the run set. Benchmark suites cite a registry release.

---

## 3. The grading contract (how the factual layer consumes this)

A Family 8 benchmark task is authored as:

> *"Compute `{definition}@{version}` over `{scope}` using registry release `{release}`."*

Grading:
1. Gold answer = **`reference_impl` run under the frozen version + pinned runs** (never a hand-written answer key).
2. Agent answer graded by the entry's `cleanliness_contract.grader`:
   - `exact` — set/scalar/categorical identity (e.g., the `target_class` label, the target list).
   - `set_match` — membership match for set outputs.
   - `score_within_tol` — numeric within `tolerance` (required for `score` outputs like CPI to absorb floating-point/run noise).
3. **Citation check** — the agent must name the `id@version` it computed against; wrong/missing version = fail even if the number is right (it computed the wrong thing).

This is what makes the task `C-def`: the *computation* is graded exactly; the *choice* of definition is out of scope (it was frozen upstream and lives in the methodological layer).

---

## 4. Dependency DAG (build bottom-up; freeze bottom-up)

```
constants / tables (atomic):
  issue_to_bill_mapping     mrp_reliability_cutoff     classification_thresholds

derived L1:
  district_opinion       ← issue_to_bill_mapping, mrp_reliability_cutoff, [mrp_run]
  member_issue_position  ← issue_to_bill_mapping, [ideal_point_run | votes]
  vulnerability          ← district_profile (margin, contested, term-limit)
  salience_w             ← district_profile (licensed-share | survey salience)

derived L2:
  position_gap           ← member_issue_position, district_opinion        # signed, standardized
  perception_gap (SENS.) ← district_opinion, [survey_wave]                # Broockman-Skovron term

top:
  cross_pressure_index   ← position_gap, salience_w, vulnerability, perception_gap   # CPI (continuous)
  target_class           ← position_gap, perception_gap, vulnerability, classification_thresholds
                           # {information_target, pressure_target, low_leverage, aligned}
```

CPI is the continuous ranking score; `target_class` is the actionable classification. Both are headline outputs (per §10 of the spec).

---

## 5. v1 seed registry

> Eleven entries, in the cross-pressure vocabulary of `statehouse-intel-repo-spec.md` §10. Every numeric value is `# PLACEHOLDER` pending expert sign-off. Formulas are v1 proposals — the *structure* is the contribution; the *parameters* are what the methodological layer argues about.

```yaml
# ---------- atomic ----------
- id: issue_to_bill_mapping
  version: "1.0.0"
  output_type: mapping
  definition_kind: mapping_table
  spec: "table: bill_id -> {issue_code, confidence in [0,1]}; multi-issue bills allowed (one row per issue)."
  inputs: [{name: bills, source: structured_core, ref: bills.ci_bill_id, run_bound: false}]
  unit_scale: "categorical issue codes (taxonomy in config/states/la.yaml)"
  rationale: "Connects a vote/position on a bill to a district's opinion on an issue. Keyword + LLM classification into the config taxonomy (licensing/occupational, fiscal, criminal justice, education, other)."
  contested_parameters:
    - {param: "issue taxonomy", current_value: "# PLACEHOLDER config taxonomy", plausible_alternatives: ["CAP subtopics", "custom liberty-issue set"], why_contested: "the taxonomy frames everything downstream; build symmetric across partisan valence"}
    - {param: "multi-issue handling", current_value: "one row per issue with confidence", why_contested: "omnibus bills dilute issue signal"}
  cleanliness_contract: {tier: C-def, grader: exact, citation_required: true}
  sensitive_data: false

- id: mrp_reliability_cutoff
  version: "1.0.0"
  output_type: scalar
  definition_kind: constant
  spec: "An MRP estimate is 'thin' if credible-interval half-width > 0.10."   # PLACEHOLDER
  inputs: [{name: mrp, source: mrp_store, ref: mrp.ci_halfwidth, run_bound: true}]
  unit_scale: "proportion points on the MRP scale"
  rationale: "Below this reliability, an estimate should not drive a leverage claim; treat district opinion as undefined."
  contested_parameters:
    - {param: "metric", current_value: "CI half-width", plausible_alternatives: ["effective cell N", "posterior SD"], why_contested: "reliability proxies disagree on small cells"}
    - {param: "cutoff", current_value: "0.10  # PLACEHOLDER", plausible_alternatives: ["0.05", "0.15"], why_contested: "trades coverage vs. confidence"}
  cleanliness_contract: {tier: C-def, grader: exact, citation_required: true}

- id: classification_thresholds
  version: "1.0.0"
  output_type: mapping
  definition_kind: constant
  spec: |
    {pg_small, pg_large, perc_large, vuln_high}  # boundaries for target_class
    # |position_gap| <= pg_small -> aligned; >= pg_large -> divergent
    # perception_gap >= perc_large -> "misperceives"; vulnerability >= vuln_high -> "exposed"
  inputs: []
  unit_scale: "thresholds on the standardized position_gap / perception_gap / vulnerability scales"
  rationale: "Defines the target_class boundaries. Replaces the old single 'divergence threshold' with the full set the classification needs; reported transparently per §10."
  contested_parameters:
    - {param: "pg_small / pg_large", current_value: "0.25 / 0.75  # PLACEHOLDER", why_contested: "what counts as aligned vs divergent on the standardized gap"}
    - {param: "perc_large", current_value: "0.10  # PLACEHOLDER", why_contested: "how wrong a member must be to count as misperceiving"}
    - {param: "vuln_high", current_value: "0.50  # PLACEHOLDER", why_contested: "what counts as electorally exposed"}
  cleanliness_contract: {tier: C-def, grader: exact, citation_required: true}

# ---------- derived L1 ----------
- id: district_opinion
  version: "1.0.0"
  output_type: score
  definition_kind: derivation
  spec: |
    For (district, issue): the MRP posterior-mean support proportion, with reliability flag.
    If thin (mrp_reliability_cutoff), district_opinion is undefined (downstream -> low_leverage / no claim).
  inputs: [{name: mrp, source: mrp_store, ref: mrp.estimate, run_bound: true}]
  depends_on: ["issue_to_bill_mapping@1.0.0", "mrp_reliability_cutoff@1.0.0"]
  run_bindings: {mrp_run: "# PLACEHOLDER la_issues_run"}
  unit_scale: "[0,1] support proportion (+ reliability flag)"
  rationale: "District's demonstrated preference from MRP outputs; honestly concedes the no-signal band."
  contested_parameters:
    - {param: "CI handling", current_value: "point estimate  # PLACEHOLDER", plausible_alternatives: ["require CI to clear a margin"], why_contested: "point vs interval changes how many districts get a verdict"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

- id: member_issue_position
  version: "1.0.0"
  output_type: score
  definition_kind: derivation
  spec: |
    For (member, issue): the member's standardized issue position — θ_issue (issue-specific
    ideal point) where the subset has >=25 informative votes; else θ_general; else revealed
    floor-vote position on issue-mapped bills (confidence >= 0.6). Report unknown if none.
  inputs: [{name: ideal_point, source: ideal_point_store, ref: ideal_point.theta, run_bound: true},
           {name: votes, source: structured_core, ref: vote_records.value, run_bound: false}]
  depends_on: ["issue_to_bill_mapping@1.0.0"]
  run_bindings: {ideal_point_run: "# PLACEHOLDER shor_mccarty_run"}
  unit_scale: "standardized position on the issue axis (common-space)"
  rationale: "Member's revealed/estimated position. Honors the spec's IRT stance: insufficient_votes reported, never imputed (no DIME in v1)."
  contested_parameters:
    - {param: "theta source order", current_value: "theta_issue -> theta_general -> votes  # PLACEHOLDER", why_contested: "issue-specific vs general ideology"}
    - {param: "min informative votes", current_value: "25", why_contested: "below this, issue-specific theta is noise"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

- id: vulnerability
  version: "1.0.0"
  output_type: score
  definition_kind: formula
  spec: |
    vulnerability = clamp01( composite(margin_history, contested_flags, term_limit_status) )  # LA-parameterized  # PLACEHOLDER
    # LA jungle-primary structure parameterized in config/states/la.yaml
  inputs: [{name: profile, source: district_profile, ref: district_profile.*, run_bound: false}]
  unit_scale: "[0,1], higher = more electorally exposed"
  rationale: "Cross-pressure is more actionable on an exposed member. Drawn from district_profile per §10."
  contested_parameters:
    - {param: "composite form", current_value: "weighted sum  # PLACEHOLDER", plausible_alternatives: ["logistic"], why_contested: "LA jungle primary makes 'primary vulnerability' state-specific"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

- id: salience_w
  version: "1.0.0"
  output_type: score
  definition_kind: formula
  spec: |
    salience_w = district issue-salience proxy.
    v1: licensed-worker share for licensing issues (from district_occupation);
    survey salience item when a wave provides one.   # PLACEHOLDER mapping per issue
  inputs: [{name: occ, source: district_profile, ref: district_profile.licensed_share, run_bound: false}]
  depends_on: ["issue_to_bill_mapping@1.0.0"]
  unit_scale: "[0,1], higher = issue more salient in the district"
  rationale: "Weights cross-pressure by how much the district actually cares about the issue."
  contested_parameters:
    - {param: "salience proxy per issue", current_value: "# PLACEHOLDER (licensed-share for licensing; TBD others)", why_contested: "proxy quality varies by issue; survey salience preferred when available"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

# ---------- derived L2 ----------
- id: position_gap
  version: "1.0.0"
  output_type: score
  definition_kind: derivation
  spec: |
    position_gap = standardize( member_issue_position - district_opinion_on_same_axis )   # signed
    # sign convention: > 0 means the member sits on the side AGAINST the district's majority.
    # undefined if member_issue_position unknown or district_opinion thin.
  inputs: []
  depends_on: ["member_issue_position@1.0.0", "district_opinion@1.0.0"]
  unit_scale: "signed, standardized; |value| = degree of divergence, sign = direction"
  rationale: "The core position-vs-district gap (replaces the old boolean 'divergence'). Continuous, signed, standardized, per §10."
  contested_parameters:
    - {param: "standardization", current_value: "z over chamber  # PLACEHOLDER", plausible_alternatives: ["min-max", "raw proportion gap"], why_contested: "scale choice affects thresholds downstream"}
    - {param: "axis alignment", current_value: "project opinion onto issue axis  # PLACEHOLDER", why_contested: "member theta and district support live on different native scales"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

- id: perception_gap
  version: "1.0.0"
  output_type: score
  definition_kind: derivation
  sensitive_data: true                 # uses legislator polling in the segregated root
  spec: |
    perception_gap = | legislator_believed_district_support - district_opinion |
    # null until the legislator survey wave lands; null members excluded from information_target.
  inputs: [{name: belief, source: survey_root, ref: legislator_survey.believed_support, run_bound: true}]
  depends_on: ["district_opinion@1.0.0"]
  run_bindings: {survey_wave: "# PLACEHOLDER", mrp_run: "# PLACEHOLDER"}
  unit_scale: "[0,1], higher = legislator more wrong about their district"
  rationale: "Broockman-Skovron misperception term (the spec's perception_gap). The strongest lever when measured: show a member their district disagrees with what they believe."
  provenance: ["Broockman & Skovron (2018) APSR", "statehouse-intel-repo-spec.md §10"]
  contested_parameters:
    - {param: "missing-belief handling", current_value: "null when unpolled  # PLACEHOLDER", why_contested: "most members are unpolled; absence is not zero"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

# ---------- top ----------
- id: cross_pressure_index
  version: "1.0.0"
  output_type: score
  definition_kind: formula
  spec: |
    CPI = clamp01( w_pos*abs(position_gap_norm) + w_sal*salience_w
                 + w_vuln*vulnerability + w_perc*perception_gap_norm )   # weights config, sum to 1
    # perception_gap term -> 0 when unpolled (renormalize remaining weights).
  inputs: [{name: mrp, source: mrp_store, ref: mrp.estimate, run_bound: true}]
  depends_on: ["position_gap@1.0.0", "salience_w@1.0.0", "vulnerability@1.0.0", "perception_gap@1.0.0"]
  run_bindings: {mrp_run: "# PLACEHOLDER", ideal_point_run: "# PLACEHOLDER"}
  unit_scale: "[0,1], the continuous cross-pressure ranking score"
  rationale: "Weighted combination of the four components (the spec's CPI). Carries intervals from theta and MRP posteriors; never report a point rank without its interval."
  provenance: ["statehouse-intel-repo-spec.md §10"]
  contested_parameters:
    - {param: "weights (w_pos,w_sal,w_vuln,w_perc)", current_value: "equal  # PLACEHOLDER", plausible_alternatives: ["position-dominant", "vulnerability-dominant"], why_contested: "the core editorial choice; sensitivity analysis in report appendix"}
    - {param: "combine form", current_value: "additive  # PLACEHOLDER", plausible_alternatives: ["multiplicative interaction"], why_contested: "independence vs interaction of components"}
  cleanliness_contract: {tier: C-def, grader: score_within_tol, tolerance: 0.001, citation_required: true}

- id: target_class
  version: "1.0.0"
  output_type: categorical
  definition_kind: derivation
  spec: |
    Given position_gap, perception_gap (nullable), vulnerability, classification_thresholds:
      if |position_gap| <= pg_small:                                              "aligned"
      elif perception_gap not null and perception_gap >= perc_large
           and |position_gap| <= pg_large:                                        "information_target"
      elif |position_gap| >= pg_large
           and (perception_gap is null or perception_gap < perc_large)
           and vulnerability >= vuln_high:                                        "pressure_target"
      else:                                                                       "low_leverage"
  inputs: []
  depends_on: ["position_gap@1.0.0", "perception_gap@1.0.0", "vulnerability@1.0.0", "classification_thresholds@1.0.0"]
  unit_scale: "{information_target, pressure_target, low_leverage, aligned}"
  rationale: |
    The actionable classification (the spec's target_class). information_target = member
    misperceives the district (inform them); pressure_target = member knows and votes against
    anyway, and is exposed (pressure them). This is the Broockman-Skovron decomposition made
    operational, and the headline output of the leverage analysis.
  provenance: ["statehouse-intel-repo-spec.md §10", "Broockman & Skovron (2018) APSR"]
  contested_parameters:
    - {param: "classification logic", current_value: "as above  # PLACEHOLDER", plausible_alternatives: ["continuous score bands off CPI"], why_contested: "rule order changes borderline assignments"}
  cleanliness_contract: {tier: C-def, grader: exact, citation_required: true}
```

---

## 6. How the methodological layer produces an entry

The lifecycle of one definition, end to end:

1. **Draft** — engineer writes the entry with a v1 `spec` and `# PLACEHOLDER` parameters (often lifting the current value straight from the statehouse-intel config it formalizes).
2. **Implement** — `reference_impl` + a `test_vector` (fixed inputs → fixed output) so the computation is reproducible.
3. **Sensitivity** — run the computation across the `plausible_alternatives` for each contested param; record how the output (e.g., the ranked target list, the class assignments) moves. This artifact is what experts actually react to.
4. **Review** — domain/academic partners set each contested parameter and bless the form. Their sign-off is the methodological-layer grade.
5. **Freeze** — gate in §8 passes; `frozen: true`, `frozen_at` set.
6. **Consume** — factual-layer Family 8 tasks now cite `id@version`; gold answers come from `reference_impl`.

---

## 7. Why this is the seam (one paragraph for humans)

Everything contestable about "find legislators against their districts" is pushed **up** into this registry and **frozen**, so everything **downstream** is exact arithmetic. The factual layer never argues about where the `pg_large` boundary sits — it computes `target_class@1.0.0`, which already encodes that choice via `classification_thresholds@1.0.0`, and grades the computation. The methodological layer never re-derives the arithmetic — it argues about and blesses the frozen choices (the CPI weights, the thresholds, the issue taxonomy). The registry is the single object both layers point at, which is why it is the bridge between them and the prerequisite for any leverage benchmark task. It is also the same config the statehouse-intel pipeline already needs — here it just gains versioning, a freeze gate, and a grading contract.

---

## 8. Freeze checklist (per entry)

- [ ] Every `contested_parameter` has a set value (no `# PLACEHOLDER` left).
- [ ] `reference_impl` exists and is deterministic.
- [ ] `test_vector` exists and passes.
- [ ] `run_bindings` pinned (if `run_bound`).
- [ ] All `depends_on` entries are already `frozen`.
- [ ] `sensitivity` analysis attached.
- [ ] ≥1 reviewer in `reviewers`.
- [ ] If `sensitive_data`, sensitive-root access path reviewed.
- [ ] Added to a named registry release (e.g., `LA-v1`).

---

## 9. Open decisions to settle before `LA-v1` freeze

These are the parameters that matter most and that only domain experts can set:

1. **Issue taxonomy** (`issue_to_bill_mapping`) — the frame for everything. Build symmetric across partisan valence.
2. **Classification thresholds** (`classification_thresholds`: pg_small, pg_large, perc_large, vuln_high) — the boundaries that decide who is an information vs pressure target. The most consequential set.
3. **District opinion CI handling** (`district_opinion`) — point estimate vs requiring the interval to clear a margin.
4. **Position construction** (`member_issue_position`, `position_gap`) — θ_issue vs θ_general order; standardization and axis-alignment method.
5. **Vulnerability composite** (`vulnerability`) — LA jungle-primary parameterization.
6. **Salience proxy per issue** (`salience_w`) — proxy quality varies; survey salience preferred when available.
7. **CPI weights and combine form** (`cross_pressure_index`).
8. **perception_gap inclusion** — it is the strongest lever but null for most members until the legislator survey wave lands; decide how absence is handled in CPI and `target_class`.
