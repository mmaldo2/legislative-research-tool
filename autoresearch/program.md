# Autoresearch: Bill Outcome Prediction

## Your Role

You are an autonomous research agent working on a bill outcome prediction model
for a legislative research platform. Your goal is to maximize the AUROC score on
the validation set while maintaining good calibration (low Brier score).

## Setup (run once at start)

1. Read this file completely
2. Read `autoresearch/prepare.py` to understand the data schema and evaluation
3. Read the current `autoresearch/train.py` to understand the baseline
4. Run the baseline: `cd autoresearch && python train.py`
5. Note the baseline AUROC and Brier score

## Experiment Loop

Repeat this cycle:

1. **Hypothesize**: Based on previous results, form a hypothesis about what
   change might improve performance. Write your hypothesis as a comment at the
   top of train.py.

2. **Modify**: Edit ONLY `autoresearch/train.py`. Do not touch prepare.py.

3. **Run**: Execute `python train.py` and observe the results.

4. **Record**: The harness automatically logs results to experiments/.
   Check if AUROC improved.

5. **Decide**: If improved, keep the changes. If not, revert train.py and
   try a different approach.

## Research Priorities (ordered)

1. **Feature engineering over model complexity.** The baseline LightGBM is
   already a strong model. Better features will help more than fancier models
   in most cases. Ideas to explore:
   - Sponsor's historical bill success rate (requires a self-join on sponsors x outcomes)
   - Committee-level passage rates (some committees kill everything, some pass everything)
   - Session timing features (bills introduced early vs late in session)
   - Jurisdiction-level base rates (some states pass more bills)
   - Text-derived features from title (length, complexity, keywords)
   - Bipartisan cosponsorship patterns (strongest known predictor in poli-sci literature)

   **Note on LLM-enriched features**: The platform stores AI analyses in the
   `ai_analyses` table (not directly on the `bills` table). To use LLM-enriched
   features (summaries, topics, constitutional flags), you would need to add a
   JOIN to `ai_analyses` in prepare.py — but since prepare.py is fixed, focus
   on metadata and sponsor features for now. These are historically sufficient
   for strong baselines.

2. **Calibration.** A model that says "30% chance" should be right 30% of the
   time. After getting AUROC above 0.80, focus on calibration:
   - Platt scaling
   - Isotonic regression
   - Temperature scaling
   - Check calibration_bins in metrics.json

3. **Robustness.** The model should work across sessions:
   - Test on different congress subsets separately
   - Check if performance degrades for specific congresses
   - Ensure the model doesn't overfit to session-specific quirks

## Constraints

- Do NOT modify prepare.py
- Do NOT access the test set (2024 data) — it's reserved for final evaluation
- Keep train.py self-contained — all logic in one file
- If an experiment fails to run, revert and try something simpler
- Log your reasoning as comments in train.py

## Data Schema (actual column names)

The feature query in prepare.py returns these columns:

| Column | Type | Source |
|--------|------|--------|
| bill_id | str | bills.id |
| jurisdiction_id | str | bills.jurisdiction_id (always 'us' for now) |
| session_id | str | bills.session_id (e.g., 'us-118') |
| identifier | str | bills.identifier (e.g., 'HR1234') |
| title | str | bills.title |
| classification | str[] | bills.classification |
| subject | str[] | bills.subject (LOC-assigned topics) |
| status | str | bills.status (canonical: introduced, in_committee, passed_lower, etc.) |
| introduced_date | date | bills.introduced_date |
| session_start | date | sessions.start_date |
| session_end | date | sessions.end_date |
| committee_passage | int | 1 if status in (passed_lower, passed_upper, enrolled, enacted, vetoed) |
| sponsor_party | str | people.party via sponsorships (D, R, or NULL) |
| cosponsor_count | int | count of cosponsors |
| bipartisan_cosponsor_count | int | count of cross-party cosponsors |
| action_count | int | total bill actions |
| first_action_date | date | earliest action |
| last_action_date | date | latest action |

## Context

This model will be a user-facing feature in a legislative research platform
targeting policy organizations (think tanks, advocacy groups like FIRE, Students
for Liberty, Pelican Institute). Researchers will see "this bill has a X% chance
of clearing committee" in the UI. Calibration and interpretability matter as
much as raw accuracy — researchers need to trust and understand the predictions.

The data comes from GovInfo BILLSTATUS XML, covering Congress 110-118
(2007-2024) with sponsor/cosponsor data extracted during ingestion.
