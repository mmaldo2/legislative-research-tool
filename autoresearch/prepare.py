"""
prepare.py — Fixed evaluation harness for bill outcome prediction.
DO NOT MODIFY. The agent modifies train.py only.

Responsibilities:
1. Connect to the existing Postgres database (same docker-compose instance)
2. Extract features from bills, sponsors, actions
3. Enforce temporal train/validation/test splits
4. Provide a standardized evaluation function
5. Log experiment results

Schema reference: src/models/ in the legislative-research-tool codebase.
"""

import datetime
import json
import os
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from sklearn.calibration import calibration_curve
from sklearn.metrics import brier_score_loss, classification_report, roc_auc_score

# ============================================================================
# CONSTANTS — Fixed experimental parameters
# ============================================================================


def _get_db_url() -> str:
    """Read DATABASE_URL and strip asyncpg dialect for psycopg2 compatibility."""
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://legis:legis_dev@localhost:5432/legis",
    )
    return re.sub(r"\+asyncpg", "", url)


DB_URL = _get_db_url()

# Temporal splits — agent CANNOT change these
TRAIN_END = "2022-12-31"
VAL_START = "2023-01-01"
VAL_END = "2023-12-31"
TEST_START = "2024-01-01"  # Hold-out test — never used during autoresearch
TEST_END = "2024-12-31"

# Prediction target: did the bill advance beyond committee?
# Based on normalize_bill_status() canonical values in src/ingestion/normalizer.py
TARGET = "committee_passage"

POSITIVE_STATUSES = ("passed_lower", "passed_upper", "enrolled", "enacted", "vetoed")
NEGATIVE_STATUSES = ("introduced", "in_committee", "failed", "withdrawn")
# "other" is excluded as ambiguous

# Experiment logging
EXPERIMENTS_DIR = Path("autoresearch/experiments")


# ============================================================================
# DATA LOADING — Pulls from existing Postgres tables
# ============================================================================


def get_connection():
    """Connect to the same Postgres instance used by the main platform."""
    return psycopg2.connect(DB_URL)


def load_raw_data() -> pd.DataFrame:
    """
    Pull bill-level data with features from the existing schema.

    Returns a DataFrame where each row is a bill with:
    - Metadata: jurisdiction, session, identifier, classification
    - Sponsor features: primary sponsor party, cosponsor count, bipartisan count
    - Action features: action count, first/last action dates
    - Target: committee_passage (binary)

    Only includes:
    - Federal bills (jurisdiction_id = 'us')
    - Bills classified as ['bill'] (excludes resolutions)
    - Bills from completed congresses (session end_date < NOW())
    - Bills with a non-ambiguous status (excludes 'other')
    - Bills with an introduced_date (for temporal splitting)
    """
    query = """
    WITH bill_features AS (
        SELECT
            b.id AS bill_id,
            b.jurisdiction_id,
            b.session_id,
            b.identifier,
            b.title,
            b.classification,
            b.subject,
            b.status,
            b.introduced_date,
            s.start_date AS session_start,
            s.end_date AS session_end
        FROM bills b
        JOIN sessions s ON b.session_id = s.id
        WHERE b.jurisdiction_id = 'us'
          AND s.end_date IS NOT NULL
          AND s.end_date < CURRENT_DATE
          AND b.introduced_date IS NOT NULL
          AND b.status IS NOT NULL
          AND b.status != 'other'
          AND b.classification @> ARRAY['bill']
    ),
    sponsor_features AS (
        SELECT
            sp.bill_id,
            p.party AS sponsor_party,
            COUNT(DISTINCT sp2.person_id) AS cosponsor_count,
            COUNT(DISTINCT CASE WHEN p2.party != p.party THEN sp2.person_id END)
                AS bipartisan_cosponsor_count
        FROM sponsorships sp
        JOIN people p ON sp.person_id = p.id AND sp.classification = 'primary'
        LEFT JOIN sponsorships sp2
            ON sp2.bill_id = sp.bill_id AND sp2.classification = 'cosponsor'
        LEFT JOIN people p2 ON sp2.person_id = p2.id
        GROUP BY sp.bill_id, p.party
    ),
    action_features AS (
        SELECT
            ba.bill_id,
            COUNT(*) AS action_count,
            MIN(ba.action_date) AS first_action_date,
            MAX(ba.action_date) AS last_action_date
        FROM bill_actions ba
        GROUP BY ba.bill_id
    )
    SELECT
        bf.*,
        CASE WHEN bf.status IN ('passed_lower','passed_upper','enrolled','enacted','vetoed')
             THEN 1 ELSE 0 END AS committee_passage,
        sf.sponsor_party,
        COALESCE(sf.cosponsor_count, 0) AS cosponsor_count,
        COALESCE(sf.bipartisan_cosponsor_count, 0) AS bipartisan_cosponsor_count,
        COALESCE(af.action_count, 0) AS action_count,
        af.first_action_date,
        af.last_action_date
    FROM bill_features bf
    LEFT JOIN sponsor_features sf ON bf.bill_id = sf.bill_id
    LEFT JOIN action_features af ON bf.bill_id = af.bill_id
    ORDER BY bf.introduced_date, bf.bill_id;
    """
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df


def split_data(df: pd.DataFrame) -> tuple:
    """
    Temporal train/val/test split. Agent CANNOT change the split boundaries.
    Bills with NULL introduced_date are dropped.
    Returns (train_df, val_df, test_df).
    """
    df = df.dropna(subset=["introduced_date"])

    train_end = pd.Timestamp(TRAIN_END)
    val_start = pd.Timestamp(VAL_START)
    val_end = pd.Timestamp(VAL_END)
    test_start = pd.Timestamp(TEST_START)
    test_end = pd.Timestamp(TEST_END)

    intro = pd.to_datetime(df["introduced_date"])

    train = df[intro <= train_end].copy()
    val = df[(intro >= val_start) & (intro <= val_end)].copy()
    test = df[(intro >= test_start) & (intro <= test_end)].copy()

    return train, val, test


# ============================================================================
# EVALUATION — The metric the agent optimizes against
# ============================================================================


def evaluate(y_true: np.ndarray, y_pred_proba: np.ndarray) -> dict:
    """
    Compute evaluation metrics. The agent sees these after each experiment.

    Primary metric: AUROC (discrimination — can the model rank bills correctly?)
    Secondary metrics:
    - Brier score (calibration — are the probabilities accurate?)
    - Calibration curve bins (is 30% really 30%?)
    - Classification report at 0.5 threshold

    For the user-facing feature, calibration matters as much as discrimination.
    A well-calibrated model lets researchers trust the displayed probabilities.
    """
    metrics = {}

    # Primary metric — this is what the agent optimizes
    metrics["auroc"] = float(roc_auc_score(y_true, y_pred_proba))

    # Calibration
    metrics["brier_score"] = float(brier_score_loss(y_true, y_pred_proba))

    # Calibration curve (10 bins)
    try:
        prob_true, prob_pred = calibration_curve(
            y_true, y_pred_proba, n_bins=10, strategy="quantile"
        )
        metrics["calibration_bins"] = {
            "predicted": prob_pred.tolist(),
            "observed": prob_true.tolist(),
        }
    except ValueError:
        metrics["calibration_bins"] = {"predicted": [], "observed": []}

    # Classification report at default threshold
    y_pred_binary = (y_pred_proba >= 0.5).astype(int)
    report = classification_report(y_true, y_pred_binary, output_dict=True, zero_division=0)
    metrics["precision_positive"] = report.get("1", {}).get("precision", 0)
    metrics["recall_positive"] = report.get("1", {}).get("recall", 0)
    metrics["f1_positive"] = report.get("1", {}).get("f1-score", 0)

    # Data summary
    metrics["n_samples"] = len(y_true)
    metrics["positive_rate"] = float(y_true.mean())

    return metrics


# ============================================================================
# EXPERIMENT LOGGING — Tracks all runs for comparison
# ============================================================================


def log_experiment(metrics: dict, train_py_path: str = "autoresearch/train.py") -> str:
    """
    Save experiment results with a snapshot of the code that produced them.
    Returns the experiment directory path.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    exp_dir = EXPERIMENTS_DIR / timestamp
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Save metrics
    with open(exp_dir / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    # Snapshot the train.py that produced these results
    if Path(train_py_path).exists():
        shutil.copy2(train_py_path, exp_dir / "train.py")

    # Append to summary log
    summary_path = EXPERIMENTS_DIR / "summary.jsonl"
    summary_entry = {
        "timestamp": timestamp,
        "auroc": metrics["auroc"],
        "brier_score": metrics["brier_score"],
        "n_samples": metrics["n_samples"],
        "positive_rate": metrics["positive_rate"],
    }
    with open(summary_path, "a") as f:
        f.write(json.dumps(summary_entry) + "\n")

    return str(exp_dir)


def get_best_auroc() -> float:
    """Return the best AUROC achieved so far across all experiments."""
    summary_path = EXPERIMENTS_DIR / "summary.jsonl"
    if not summary_path.exists():
        return 0.0
    best = 0.0
    with open(summary_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry["auroc"] > best:
                best = entry["auroc"]
    return best


# ============================================================================
# CONVENIENCE — Called by train.py
# ============================================================================


def get_data():
    """Main entry point for train.py. Returns prepared train/val splits."""
    df = load_raw_data()
    train_df, val_df, _test_df = split_data(df)
    print(f"Loaded {len(train_df)} training bills, {len(val_df)} validation bills")
    print(f"Training positive rate: {train_df[TARGET].mean():.3f}")
    print(f"Validation positive rate: {val_df[TARGET].mean():.3f}")
    print(f"Current best AUROC: {get_best_auroc():.4f}")
    return train_df, val_df


def run_evaluation(y_true, y_pred_proba) -> dict:
    """Evaluate and log. Returns metrics dict."""
    metrics = evaluate(y_true, y_pred_proba)
    exp_dir = log_experiment(metrics)

    best = get_best_auroc()
    improved = metrics["auroc"] > best

    print(f"\n{'=' * 60}")
    print(f"RESULTS — AUROC: {metrics['auroc']:.4f} | Brier: {metrics['brier_score']:.4f}")
    print(f"Precision: {metrics['precision_positive']:.3f} | Recall: {metrics['recall_positive']:.3f}")
    print(f"{'IMPROVED!' if improved else 'No improvement.'} (previous best: {best:.4f})")
    print(f"Experiment saved to: {exp_dir}")
    print(f"{'=' * 60}\n")

    return metrics
