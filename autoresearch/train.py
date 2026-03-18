"""
train.py — Bill outcome prediction model.
THIS FILE IS MODIFIED BY THE AI AGENT. Everything else is fixed.

Current approach: Gradient boosted trees (LightGBM) with basic features.
The agent should experiment with:
- Feature engineering (text features, network features, temporal features)
- Model architecture (try XGBoost, random forests, logistic regression, small neural nets)
- Hyperparameter tuning
- Feature selection and dimensionality reduction
- Handling class imbalance (SMOTE, class weights, threshold tuning)
- Ensemble methods
- Creating interaction features
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from prepare import get_data, run_evaluation, TARGET

# ============================================================================
# FEATURE ENGINEERING
# ============================================================================


def build_features(df: pd.DataFrame) -> tuple:
    """
    Convert raw bill data into feature matrix.
    Returns (X, y, feature_names) where X is a numpy array and y is the target.
    """
    features = pd.DataFrame(index=df.index)

    # Sponsor features
    features["cosponsor_count"] = df["cosponsor_count"].fillna(0)
    features["bipartisan_cosponsor_count"] = df["bipartisan_cosponsor_count"].fillna(0)
    features["bipartisan_ratio"] = (
        features["bipartisan_cosponsor_count"] / (features["cosponsor_count"] + 1)
    )

    # Sponsor party (one-hot)
    features["sponsor_democrat"] = (df["sponsor_party"] == "D").astype(int)
    features["sponsor_republican"] = (df["sponsor_party"] == "R").astype(int)

    # Action features
    features["action_count"] = df["action_count"].fillna(0)

    # Title length as a crude text feature
    features["title_length"] = df["title"].str.len().fillna(0)

    # Number of assigned subjects
    features["subject_count"] = df["subject"].apply(
        lambda x: len(x) if isinstance(x, list) else 0
    )

    X = features.values.astype(np.float32)
    y = df[TARGET].values.astype(np.float32)

    return X, y, list(features.columns)


# ============================================================================
# MODEL
# ============================================================================


def train_and_predict(X_train, y_train, X_val, feature_names):
    """Train model and return validation predictions."""

    train_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)

    params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "is_unbalance": True,
    }

    model = lgb.train(
        params,
        train_data,
        num_boost_round=500,
    )

    y_pred_proba = model.predict(X_val)

    # Print feature importance for the agent to reason about
    importance = model.feature_importance(importance_type="gain")
    print("\nFeature importance:")
    for name, imp in sorted(zip(feature_names, importance), key=lambda x: -x[1]):
        print(f"  {name}: {imp:.1f}")

    return y_pred_proba


# ============================================================================
# MAIN — Run experiment
# ============================================================================

if __name__ == "__main__":
    # Load data from the harness
    train_df, val_df = get_data()

    # Build features
    X_train, y_train, feature_names = build_features(train_df)
    X_val, y_val, _ = build_features(val_df)

    print(f"Feature matrix: {X_train.shape[1]} features")
    print(f"Feature names: {feature_names}")

    # Train and predict
    y_pred_proba = train_and_predict(X_train, y_train, X_val, feature_names)

    # Evaluate (this logs the experiment automatically)
    metrics = run_evaluation(y_val, y_pred_proba)
