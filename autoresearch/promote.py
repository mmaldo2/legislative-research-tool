"""
promote.py — Export the best autoresearch model for production use.

Retrains the Experiment 8 stacking ensemble (LightGBM + RandomForest + LR)
on all available training data and saves artifacts to src/prediction/models/.

Usage: cd autoresearch && python promote.py
"""

import json
import pickle
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from prepare import evaluate, load_raw_data, split_data
from train import build_features

MODELS_DIR = Path("../src/prediction/models")
N_FOLDS = 7


def promote():
    """Train the production model and export artifacts."""
    print("Loading data...")
    df = load_raw_data()
    train_df, val_df, test_df = split_data(df)

    # Train on train+val combined for production
    combined_df = __import__("pandas").concat([train_df, val_df])
    X, y, feature_names = build_features(combined_df)
    print(f"Training on {len(X)} bills, {y.sum():.0f} positives ({y.mean()*100:.1f}%)")

    pos_count = y.sum()
    neg_count = len(y) - pos_count
    scale_ratio = neg_count / max(pos_count, 1)

    lgbm_params = {
        "objective": "binary",
        "metric": "auc",
        "verbosity": -1,
        "num_leaves": 63,
        "learning_rate": 0.03,
        "feature_fraction": 0.7,
        "bagging_fraction": 0.7,
        "bagging_freq": 5,
        "scale_pos_weight": scale_ratio,
        "min_child_samples": 10,
        "lambda_l1": 0.1,
        "lambda_l2": 0.1,
    }

    # ---- Train fold models for stacking ----
    print(f"Training {N_FOLDS}-fold stacking ensemble...")
    oof_lgbm = np.zeros(len(y))
    oof_rf = np.zeros(len(y))
    lgbm_models = []
    rf_models = []

    kf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)

    for fold, (tr_idx, vl_idx) in enumerate(kf.split(X, y)):
        X_tr, X_vl = X[tr_idx], X[vl_idx]
        y_tr, y_vl = y[tr_idx], y[vl_idx]

        # LightGBM
        tr_data = lgb.Dataset(X_tr, label=y_tr, feature_name=feature_names)
        vl_data = lgb.Dataset(X_vl, label=y_vl, feature_name=feature_names, reference=tr_data)
        lgbm_model = lgb.train(
            lgbm_params,
            tr_data,
            num_boost_round=2000,
            valid_sets=[vl_data],
            callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)],
        )
        oof_lgbm[vl_idx] = lgbm_model.predict(X_vl)
        lgbm_models.append(lgbm_model)

        # RandomForest
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            class_weight="balanced",
            random_state=42 + fold,
            n_jobs=-1,
        )
        rf.fit(X_tr, y_tr)
        oof_rf[vl_idx] = rf.predict_proba(X_vl)[:, 1]
        rf_models.append(rf)

        print(f"  Fold {fold + 1}: lgbm_iter={lgbm_model.best_iteration}")

    # ---- Train meta-learner ----
    print("Training meta-learner...")
    action_idx = feature_names.index("log_action_count")
    cosponsor_idx = feature_names.index("log_cosponsor_count")
    interact_idx = feature_names.index("early_bill_x_actions")

    meta_features = np.column_stack(
        [
            oof_lgbm,
            oof_rf,
            oof_lgbm * oof_rf,
            X[:, action_idx],
            X[:, cosponsor_idx],
            X[:, interact_idx],
        ]
    )

    scaler = StandardScaler()
    meta_scaled = scaler.fit_transform(meta_features)

    lr = LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)
    lr.fit(meta_scaled, y)

    # ---- Evaluate on test set ----
    if len(test_df) > 10:
        X_test, y_test, _ = build_features(test_df)
        lgbm_test = np.mean([m.predict(X_test) for m in lgbm_models], axis=0)
        rf_test = np.mean([m.predict_proba(X_test)[:, 1] for m in rf_models], axis=0)
        meta_test = np.column_stack(
            [
                lgbm_test,
                rf_test,
                lgbm_test * rf_test,
                X_test[:, action_idx],
                X_test[:, cosponsor_idx],
                X_test[:, interact_idx],
            ]
        )
        test_preds = lr.predict_proba(scaler.transform(meta_test))[:, 1]
        test_metrics = evaluate(y_test, test_preds)
        print(f"\nTest set AUROC: {test_metrics['auroc']:.4f}")
        print(f"Test set Brier: {test_metrics['brier_score']:.4f}")
    else:
        test_metrics = {"auroc": None, "brier_score": None}
        print("\nTest set too small for evaluation")

    # ---- Save artifacts ----
    print(f"\nSaving to {MODELS_DIR}/...")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # LightGBM models
    lgbm_dir = MODELS_DIR / "lgbm_folds"
    lgbm_dir.mkdir(exist_ok=True)
    for i, model in enumerate(lgbm_models):
        model.save_model(str(lgbm_dir / f"fold_{i}.txt"))

    # RandomForest models
    rf_dir = MODELS_DIR / "rf_folds"
    rf_dir.mkdir(exist_ok=True)
    for i, model in enumerate(rf_models):
        with open(rf_dir / f"fold_{i}.pkl", "wb") as f:
            pickle.dump(model, f)

    # Meta-learner + scaler
    with open(MODELS_DIR / "meta_lr.pkl", "wb") as f:
        pickle.dump(lr, f)
    with open(MODELS_DIR / "meta_scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)

    # Metadata
    metadata = {
        "model_version": datetime.now().strftime("%Y-%m-%d"),
        "training_date": datetime.now().isoformat(),
        "n_folds": N_FOLDS,
        "feature_names": feature_names,
        "meta_feature_indices": {
            "log_action_count": action_idx,
            "log_cosponsor_count": cosponsor_idx,
            "early_bill_x_actions": interact_idx,
        },
        "training_samples": len(X),
        "positive_rate": float(y.mean()),
        "test_auroc": test_metrics.get("auroc"),
        "test_brier": test_metrics.get("brier_score"),
    }
    with open(MODELS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print("\nPromotion complete!")
    print(f"  {N_FOLDS} LightGBM models -> {lgbm_dir}/")
    print(f"  {N_FOLDS} RandomForest models -> {rf_dir}/")
    print(f"  Meta-learner -> {MODELS_DIR}/meta_lr.pkl")
    print(f"  Metadata -> {MODELS_DIR}/metadata.json")


if __name__ == "__main__":
    promote()
