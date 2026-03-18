"""Bill outcome prediction service.

Loads the promoted stacking ensemble model and scores individual bills
based on their current features (actions, sponsors, session timing).
"""

import json
import logging
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"

# Module-level model state (loaded once at import)
_lgbm_models: list = []
_rf_models: list = []
_meta_lr = None
_meta_scaler = None
_metadata: dict = {}
_model_loaded = False


def _load_models() -> bool:
    """Load model artifacts from disk. Returns True if successful."""
    global _lgbm_models, _rf_models, _meta_lr, _meta_scaler, _metadata, _model_loaded

    metadata_path = MODELS_DIR / "metadata.json"
    if not metadata_path.exists():
        logger.warning("No model artifacts found at %s", MODELS_DIR)
        return False

    try:
        with open(metadata_path) as f:
            _metadata = json.load(f)

        # Load LightGBM fold models
        lgbm_dir = MODELS_DIR / "lgbm_folds"
        _lgbm_models = []
        for i in range(_metadata.get("n_folds", 7)):
            model = lgb.Booster(model_file=str(lgbm_dir / f"fold_{i}.txt"))
            _lgbm_models.append(model)

        # Load RandomForest fold models
        rf_dir = MODELS_DIR / "rf_folds"
        _rf_models = []
        for i in range(_metadata.get("n_folds", 7)):
            with open(rf_dir / f"fold_{i}.pkl", "rb") as f:
                _rf_models.append(pickle.load(f))  # noqa: S301

        # Load meta-learner and scaler
        with open(MODELS_DIR / "meta_lr.pkl", "rb") as f:
            _meta_lr = pickle.load(f)  # noqa: S301
        with open(MODELS_DIR / "meta_scaler.pkl", "rb") as f:
            _meta_scaler = pickle.load(f)  # noqa: S301

        _model_loaded = True
        logger.info(
            "Loaded prediction model v%s (%d folds)",
            _metadata.get("model_version", "unknown"),
            len(_lgbm_models),
        )
        return True
    except Exception:
        logger.exception("Failed to load prediction model")
        return False


# Load on import
_load_models()


def is_model_loaded() -> bool:
    """Check if model artifacts are loaded and ready."""
    return _model_loaded


def get_model_version() -> str:
    """Return the model version string."""
    return _metadata.get("model_version", "unknown")


def get_base_rate() -> float:
    """Return the training data positive rate."""
    return _metadata.get("positive_rate", 0.0)


async def predict_bill(session: AsyncSession, bill_id: str) -> dict | None:
    """Score a single bill. Returns prediction dict or None if bill not found.

    Queries current bill features from the database and runs them through
    the stacking ensemble.
    """
    if not _model_loaded:
        return None

    # Fetch bill features with a single query
    result = await session.execute(
        text("""
            SELECT
                b.id,
                b.identifier,
                b.title,
                b.session_id,
                b.introduced_date,
                s.start_date AS session_start,
                s.end_date AS session_end,
                COALESCE(sf.cosponsor_count, 0) AS cosponsor_count,
                COALESCE(sf.bipartisan_count, 0) AS bipartisan_cosponsor_count,
                COALESCE(af.action_count, 0) AS action_count,
                af.first_action_date,
                af.last_action_date
            FROM bills b
            JOIN sessions s ON b.session_id = s.id
            LEFT JOIN (
                SELECT sp.bill_id,
                       COUNT(DISTINCT sp2.person_id) AS cosponsor_count,
                       COUNT(DISTINCT CASE WHEN p2.party != p.party THEN sp2.person_id END)
                           AS bipartisan_count
                FROM sponsorships sp
                JOIN people p ON sp.person_id = p.id AND sp.classification = 'primary'
                LEFT JOIN sponsorships sp2
                    ON sp2.bill_id = sp.bill_id AND sp2.classification = 'cosponsor'
                LEFT JOIN people p2 ON sp2.person_id = p2.id
                WHERE sp.bill_id = :bill_id
                GROUP BY sp.bill_id
            ) sf ON sf.bill_id = b.id
            LEFT JOIN (
                SELECT bill_id,
                       COUNT(*) AS action_count,
                       MIN(action_date) AS first_action_date,
                       MAX(action_date) AS last_action_date
                FROM bill_actions
                WHERE bill_id = :bill_id
                GROUP BY bill_id
            ) af ON af.bill_id = b.id
            WHERE b.id = :bill_id
        """),
        {"bill_id": bill_id},
    )
    row = result.mappings().first()
    if not row:
        return None

    # Build feature vector (must match train.py build_features exactly)
    features, feature_names = _build_single_bill_features(row)

    # Run through stacking ensemble
    probability, contributions = _predict(features, feature_names)

    # Build key factors from top contributions
    key_factors = []
    for fname, value, contrib in sorted(contributions, key=lambda x: -abs(x[2]))[:5]:
        key_factors.append(
            {
                "feature": fname,
                "value": round(float(value), 3),
                "impact": "positive" if contrib > 0 else "negative",
            }
        )

    return {
        "bill_id": bill_id,
        "committee_passage_probability": round(float(probability), 4),
        "model_version": get_model_version(),
        "key_factors": key_factors,
        "base_rate": round(get_base_rate(), 4),
    }


def _build_single_bill_features(row) -> tuple[np.ndarray, list[str]]:
    """Build the 18-feature vector for a single bill from a DB row."""
    import math

    cosponsor_count = float(row["cosponsor_count"])
    bipartisan_count = float(row["bipartisan_cosponsor_count"])
    action_count = float(row["action_count"])

    # Temporal calculations
    session_start = row["session_start"]
    session_end = row["session_end"]
    introduced = row["introduced_date"]

    if session_start and session_end and introduced:
        session_length = max((session_end - session_start).days, 1)
        days_into = max((introduced - session_start).days, 0)
        session_position = min(days_into / session_length, 1.0)
        days_remaining = max((session_end - introduced).days, 0)
    else:
        session_position = 0.5
        days_remaining = 0

    # Days active
    first_action = row["first_action_date"]
    last_action = row["last_action_date"]
    if first_action and last_action:
        days_active = max((last_action - first_action).days, 0)
    else:
        days_active = 0

    actions_per_day = action_count / max(days_active, 1)

    # Congress number from session_id
    session_id = row["session_id"] or ""
    try:
        congress_number = float(session_id.split("-")[1]) if "-" in session_id else 0
    except (IndexError, ValueError):
        congress_number = 0

    # Bill type
    identifier = (row["identifier"] or "").upper()
    is_house_bill = 1.0 if identifier.startswith("HR") else 0.0
    import re

    is_senate_bill = 1.0 if re.match(r"^S\d", identifier) else 0.0

    # Title features
    title = row["title"] or ""
    title_lower = title.lower()
    title_length = float(len(title))
    title_word_count = float(len(title.split()))

    passage_keywords = ["appropriat", "authoriz", "reauthoriz", "designat", "post office"]
    passage_keyword_count = sum(1 for kw in passage_keywords if kw in title_lower)
    title_has_authoriz = 1.0 if "authoriz" in title_lower else 0.0

    log_action_count = math.log1p(action_count)
    log_cosponsor_count = math.log1p(cosponsor_count)

    # Interaction features
    early_bill_x_actions = (1 - session_position) * log_action_count
    action_x_cosponsor = log_action_count * log_cosponsor_count

    # Build vector in same order as train.py
    feature_values = [
        cosponsor_count,
        log_cosponsor_count,
        bipartisan_count,
        action_count,
        log_action_count,
        days_active,
        actions_per_day,
        session_position,
        days_remaining,
        congress_number,
        is_house_bill,
        is_senate_bill,
        title_length,
        title_word_count,
        float(passage_keyword_count),
        title_has_authoriz,
        early_bill_x_actions,
        action_x_cosponsor,
    ]

    feature_names = [
        "cosponsor_count",
        "log_cosponsor_count",
        "bipartisan_cosponsor_count",
        "action_count",
        "log_action_count",
        "days_active",
        "actions_per_day",
        "session_position",
        "days_remaining",
        "congress_number",
        "is_house_bill",
        "is_senate_bill",
        "title_length",
        "title_word_count",
        "passage_keyword_count",
        "title_has_authoriz",
        "early_bill_x_actions",
        "action_x_cosponsor",
    ]

    return np.array([feature_values], dtype=np.float32), feature_names


def _predict(features: np.ndarray, feature_names: list[str]) -> tuple[float, list]:
    """Run features through the stacking ensemble. Returns (probability, contributions)."""
    # Layer 1: Average fold predictions
    lgbm_preds = np.mean([m.predict(features)[0] for m in _lgbm_models])
    rf_preds = np.mean([m.predict_proba(features)[0, 1] for m in _rf_models])

    # Meta-feature indices from metadata
    idx = _metadata.get("meta_feature_indices", {})
    action_idx = idx.get("log_action_count", 4)
    cosponsor_idx = idx.get("log_cosponsor_count", 1)
    interact_idx = idx.get("early_bill_x_actions", 16)

    # Layer 2: Meta-learner
    meta = np.array(
        [[
            lgbm_preds,
            rf_preds,
            lgbm_preds * rf_preds,
            features[0, action_idx],
            features[0, cosponsor_idx],
            features[0, interact_idx],
        ]]
    )
    meta_scaled = _meta_scaler.transform(meta)
    probability = _meta_lr.predict_proba(meta_scaled)[0, 1]

    # Feature contributions (approximate via feature values * direction)
    contributions = []
    for i, fname in enumerate(feature_names):
        val = features[0, i]
        # Positive contribution if feature value is above average and correlated with passage
        contrib = val * (1 if fname in (
            "action_count", "log_action_count", "cosponsor_count",
            "bipartisan_cosponsor_count", "days_active", "early_bill_x_actions",
            "passage_keyword_count", "title_has_authoriz",
        ) else -0.1)
        contributions.append((fname, val, contrib))

    return probability, contributions
