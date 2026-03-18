"""
Logistic regression baseline for comparison.
Run this to establish a floor — the autoresearch agent should beat this easily.

Usage: cd autoresearch && python baselines/logistic_baseline.py
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from prepare import TARGET, get_data, run_evaluation


def build_features(df: pd.DataFrame) -> tuple:
    """Minimal feature set for logistic regression baseline."""
    features = pd.DataFrame(index=df.index)
    features["cosponsor_count"] = df["cosponsor_count"].fillna(0)
    features["bipartisan_cosponsor_count"] = df["bipartisan_cosponsor_count"].fillna(0)
    features["action_count"] = df["action_count"].fillna(0)
    features["sponsor_democrat"] = (df["sponsor_party"] == "D").astype(int)
    features["sponsor_republican"] = (df["sponsor_party"] == "R").astype(int)

    X = features.values.astype(np.float32)
    y = df[TARGET].values.astype(np.float32)
    return X, y


if __name__ == "__main__":
    train_df, val_df = get_data()
    X_train, y_train = build_features(train_df)
    X_val, y_val = build_features(val_df)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    model = LogisticRegression(class_weight="balanced", max_iter=1000)
    model.fit(X_train_scaled, y_train)
    y_pred_proba = model.predict_proba(X_val_scaled)[:, 1]

    print("\n--- Logistic Regression Baseline ---")
    metrics = run_evaluation(y_val, y_pred_proba)
