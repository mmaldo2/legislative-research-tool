"""
train.py — Bill outcome prediction model.
THIS FILE IS MODIFIED BY THE AI AGENT. Everything else is fixed.

EXPERIMENT 8: Stacking without isotonic (it hurt AUROC in Exp 7).

Results so far:
- Exp 4 (tuned params): AUROC 0.9873
- Exp 6 (curated+F1):   AUROC 0.9883
- Exp 7 (stack+iso):    AUROC 0.9935 (but LR alone hit 0.9948!)

Hypothesis: The isotonic calibration in Exp 7 reduced AUROC from 0.9948 to
0.9935. Skip it. Also try: (1) more folds (7 instead of 5), (2) add more
meta-features to the LR stacking layer, (3) use Random Forest as a second
base learner for model diversity.
"""

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from prepare import get_data, run_evaluation, TARGET

PASSAGE_KEYWORDS = ["appropriat", "authoriz", "reauthoriz", "designat", "post office"]


def build_features(df: pd.DataFrame) -> tuple:
    """Curated features from Exp 6."""
    features = pd.DataFrame(index=df.index)

    features["cosponsor_count"] = df["cosponsor_count"].fillna(0)
    features["log_cosponsor_count"] = np.log1p(features["cosponsor_count"])
    features["bipartisan_cosponsor_count"] = df["bipartisan_cosponsor_count"].fillna(0)

    features["action_count"] = df["action_count"].fillna(0)
    features["log_action_count"] = np.log1p(features["action_count"])
    first_action = pd.to_datetime(df["first_action_date"])
    last_action = pd.to_datetime(df["last_action_date"])
    features["days_active"] = (last_action - first_action).dt.days.fillna(0)
    features["actions_per_day"] = (
        features["action_count"] / features["days_active"].clip(lower=1)
    )

    session_start = pd.to_datetime(df["session_start"])
    session_end = pd.to_datetime(df["session_end"])
    introduced = pd.to_datetime(df["introduced_date"])
    session_length = (session_end - session_start).dt.days.clip(lower=1)
    days_into = (introduced - session_start).dt.days.clip(lower=0)
    features["session_position"] = (days_into / session_length).clip(0, 1).fillna(0.5)
    features["days_remaining"] = (session_end - introduced).dt.days.clip(lower=0).fillna(0)
    features["congress_number"] = (
        df["session_id"].str.extract(r"us-(\d+)")[0].astype(float).fillna(0)
    )

    identifier = df["identifier"].str.upper()
    features["is_house_bill"] = identifier.str.startswith("HR").astype(int)
    features["is_senate_bill"] = identifier.str.match(r"^S\d").astype(int)

    features["title_length"] = df["title"].str.len().fillna(0)
    features["title_word_count"] = df["title"].str.split().str.len().fillna(0)
    title_lower = df["title"].str.lower().fillna("")
    features["passage_keyword_count"] = sum(
        title_lower.str.contains(kw, na=False).astype(int) for kw in PASSAGE_KEYWORDS
    )
    features["title_has_authoriz"] = title_lower.str.contains("authoriz", na=False).astype(int)

    features["early_bill_x_actions"] = (
        (1 - features["session_position"]) * features["log_action_count"]
    )
    features["action_x_cosponsor"] = (
        features["log_action_count"] * features["log_cosponsor_count"]
    )

    X = features.values.astype(np.float32)
    y = df[TARGET].values.astype(np.float32)
    return X, y, list(features.columns)


def train_and_predict(X_train, y_train, X_val, y_val, feature_names):
    """Two-model stacking: LightGBM + RandomForest -> Logistic Regression."""

    pos_count = y_train.sum()
    neg_count = len(y_train) - pos_count
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

    # ---- Layer 1: Out-of-fold predictions from 2 models ----
    print("Training Layer 1 (7-fold, 2 models)...")
    oof_lgbm = np.zeros(len(y_train))
    oof_rf = np.zeros(len(y_train))
    val_lgbm_list = []
    val_rf_list = []

    kf = StratifiedKFold(n_splits=7, shuffle=True, random_state=42)

    for fold, (tr_idx, vl_idx) in enumerate(kf.split(X_train, y_train)):
        X_tr, X_vl = X_train[tr_idx], X_train[vl_idx]
        y_tr, y_vl = y_train[tr_idx], y_train[vl_idx]

        # LightGBM
        tr_data = lgb.Dataset(X_tr, label=y_tr, feature_name=feature_names)
        vl_data = lgb.Dataset(X_vl, label=y_vl, feature_name=feature_names, reference=tr_data)
        lgbm_model = lgb.train(
            lgbm_params, tr_data, num_boost_round=2000,
            valid_sets=[vl_data],
            callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)],
        )
        oof_lgbm[vl_idx] = lgbm_model.predict(X_vl)
        val_lgbm_list.append(lgbm_model.predict(X_val))

        # Random Forest
        rf = RandomForestClassifier(
            n_estimators=200, max_depth=10, class_weight="balanced",
            random_state=42 + fold, n_jobs=-1,
        )
        rf.fit(X_tr, y_tr)
        oof_rf[vl_idx] = rf.predict_proba(X_vl)[:, 1]
        val_rf_list.append(rf.predict_proba(X_val)[:, 1])

        print(f"  Fold {fold+1}: lgbm_iter={lgbm_model.best_iteration}")

    lgbm_val = np.mean(val_lgbm_list, axis=0)
    rf_val = np.mean(val_rf_list, axis=0)

    # Full model for feature importance
    full_train = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)
    full_val_ds = lgb.Dataset(X_val, label=y_val, feature_name=feature_names, reference=full_train)
    full_model = lgb.train(
        lgbm_params, full_train, num_boost_round=2000,
        valid_sets=[full_val_ds],
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(0)],
    )

    importance = full_model.feature_importance(importance_type="gain")
    print("\nFeature importance (top 10):")
    for name, imp in sorted(zip(feature_names, importance), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {imp:.1f}")

    # ---- Layer 2: Stacking with meta-features ----
    print("\nTraining Layer 2 (Logistic Regression on 2-model stack)...")

    # Key feature indices for meta-features
    action_idx = feature_names.index("log_action_count")
    cosponsor_idx = feature_names.index("log_cosponsor_count")
    interact_idx = feature_names.index("early_bill_x_actions")

    meta_train = np.column_stack([
        oof_lgbm, oof_rf,
        oof_lgbm * oof_rf,  # model agreement signal
        X_train[:, action_idx],
        X_train[:, cosponsor_idx],
        X_train[:, interact_idx],
    ])
    meta_val = np.column_stack([
        lgbm_val, rf_val,
        lgbm_val * rf_val,
        X_val[:, action_idx],
        X_val[:, cosponsor_idx],
        X_val[:, interact_idx],
    ])

    scaler = StandardScaler()
    meta_train_scaled = scaler.fit_transform(meta_train)
    meta_val_scaled = scaler.transform(meta_val)

    lr = LogisticRegression(class_weight="balanced", max_iter=1000, C=1.0)
    lr.fit(meta_train_scaled, y_train)
    y_pred_proba = lr.predict_proba(meta_val_scaled)[:, 1]

    # Stage comparison
    from sklearn.metrics import roc_auc_score, brier_score_loss
    print("\nStage comparison:")
    print(f"  LightGBM avg:  AUROC={roc_auc_score(y_val, lgbm_val):.4f}  "
          f"Brier={brier_score_loss(y_val, lgbm_val):.4f}")
    print(f"  RF avg:        AUROC={roc_auc_score(y_val, rf_val):.4f}  "
          f"Brier={brier_score_loss(y_val, rf_val):.4f}")
    print(f"  LR stacking:   AUROC={roc_auc_score(y_val, y_pred_proba):.4f}  "
          f"Brier={brier_score_loss(y_val, y_pred_proba):.4f}")

    # Threshold analysis
    print("\nThreshold analysis:")
    best_f1 = 0
    best_thresh = 0.05
    for thresh_pct in range(1, 51):
        thresh = thresh_pct / 100
        pb = (y_pred_proba >= thresh).astype(int)
        tp = ((pb == 1) & (y_val == 1)).sum()
        fp = ((pb == 1) & (y_val == 0)).sum()
        fn = ((pb == 0) & (y_val == 1)).sum()
        prec = tp / max(tp + fp, 1)
        rec = tp / max(tp + fn, 1)
        f1 = 2 * prec * rec / max(prec + rec, 1e-8)
        if f1 > best_f1:
            best_f1 = f1
            best_thresh = thresh
        if thresh_pct in [1, 2, 3, 5, 7, 10, 15, 20, 50]:
            print(f"  t={thresh:.2f}: prec={prec:.3f} rec={rec:.3f} f1={f1:.3f}")
    print(f"\n  Optimal threshold: {best_thresh:.2f} (F1={best_f1:.3f})")

    return y_pred_proba


if __name__ == "__main__":
    import sys

    run_test = "--test" in sys.argv

    if run_test:
        # FINAL EVALUATION on held-out 2024 test set
        from prepare import load_raw_data, split_data, evaluate

        print("=" * 60)
        print("FINAL EVALUATION ON HELD-OUT 2024 TEST SET")
        print("=" * 60)

        df = load_raw_data()
        train_df, val_df, test_df = split_data(df)

        # Train on train+val combined (standard practice for final eval)
        combined_df = pd.concat([train_df, val_df])
        X_combined, y_combined, feature_names = build_features(combined_df)
        X_test, y_test, _ = build_features(test_df)

        print(f"Training on: {len(combined_df)} bills (train+val)")
        print(f"Testing on:  {len(test_df)} bills (2024 held-out)")
        print(f"Test positive rate: {y_test.mean():.3f}")

        y_pred = train_and_predict(X_combined, y_combined, X_test, y_test, feature_names)
        metrics = evaluate(y_test, y_pred)

        print(f"\n{'=' * 60}")
        print(f"FINAL TEST RESULTS")
        print(f"  AUROC:     {metrics['auroc']:.4f}")
        print(f"  Brier:     {metrics['brier_score']:.4f}")
        print(f"  Precision: {metrics['precision_positive']:.3f}")
        print(f"  Recall:    {metrics['recall_positive']:.3f}")
        print(f"  F1:        {metrics['f1_positive']:.3f}")
        print(f"  Samples:   {metrics['n_samples']}")
        print(f"  Pos rate:  {metrics['positive_rate']:.3f}")
        print(f"{'=' * 60}")
    else:
        train_df, val_df = get_data()
        X_train, y_train, feature_names = build_features(train_df)
        X_val, y_val, _ = build_features(val_df)

        print(f"Feature matrix: {X_train.shape[1]} features")
        print(f"Positive in val: {y_val.sum():.0f} / {len(y_val)} ({y_val.mean()*100:.1f}%)")

        y_pred_proba = train_and_predict(X_train, y_train, X_val, y_val, feature_names)
        metrics = run_evaluation(y_val, y_pred_proba)
