"""
Experiment script: Compare XGBoost vs LightGBM, feature selection, hyperparams.
Run: python -m scripts.experiment_models
"""
import logging
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
import xgboost as xgb
import lightgbm as lgb

from src.database.database import get_session
from src.database.models import MatchRaw, MatchFeature
from src.model.network import LABEL_TO_INDEX

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

ALL_FEATURES = [
    "home_pts_last_5", "home_goals_scored_last_5", "home_goals_conceded_last_5",
    "away_pts_last_5", "away_goals_scored_last_5", "away_goals_conceded_last_5",
    "home_elo", "away_elo", "elo_diff",
    "home_pts_last_5_at_home", "away_pts_last_5_away",
    "home_days_rest", "away_days_rest",
    "implied_home", "implied_draw", "implied_away",
    "home_sot_last_5", "away_sot_last_5",
    "home_sot_conceded_last_5", "away_sot_conceded_last_5",
]


def load_data():
    session = get_session()
    feature_cols = [getattr(MatchFeature, c) for c in ALL_FEATURES if hasattr(MatchFeature, c)]
    stmt = (
        select(
            MatchFeature.match_id,
            *feature_cols,
            MatchRaw.avg_h, MatchRaw.avg_d, MatchRaw.avg_a,
            MatchRaw.ftr,
        )
        .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
        .order_by(MatchRaw.date)
    )
    rows = session.execute(stmt).fetchall()
    raw_cols = ["match_id"] + [c for c in ALL_FEATURES if c not in ("implied_home", "implied_draw", "implied_away")] + ["avg_h", "avg_d", "avg_a", "ftr"]
    df = pd.DataFrame(rows, columns=raw_cols)
    df = df.dropna(subset=["avg_h", "avg_d", "avg_a"])
    margin = (1.0 / df["avg_h"]) + (1.0 / df["avg_d"]) + (1.0 / df["avg_a"])
    df["implied_home"] = (1.0 / df["avg_h"]) / margin
    df["implied_draw"] = (1.0 / df["avg_d"]) / margin
    df["implied_away"] = (1.0 / df["avg_a"]) / margin
    df = df.drop(columns=["avg_h", "avg_d", "avg_a"])
    session.close()
    return df


def split_data(df, features, test_pct=0.05, val_pct=0.10):
    df_clean = df.dropna(subset=features + ["ftr"])
    X = df_clean[features].values.astype(np.float32)
    y = df_clean["ftr"].map(LABEL_TO_INDEX).values.astype(np.int64)
    n = len(X)
    n_test = int(n * test_pct)
    n_val = int(n * val_pct)
    n_train = n - n_val - n_test
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X[:n_train])
    X_val = scaler.transform(X[n_train:n_train+n_val])
    X_test = scaler.transform(X[n_train+n_val:])
    y_train, y_val, y_test = y[:n_train], y[n_train:n_train+n_val], y[n_train+n_val:]
    return X_train, y_train, X_val, y_val, X_test, y_test


def train_xgb(X_train, y_train, X_val, y_val, **kwargs):
    class_counts = np.bincount(y_train, minlength=3)
    sample_weights = np.array([len(y_train) / (3.0 * class_counts[c]) for c in y_train])
    params = dict(
        n_estimators=500, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        reg_alpha=0.1, reg_lambda=1.0,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", early_stopping_rounds=50,
        random_state=42, n_jobs=-1,
    )
    params.update(kwargs)
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, sample_weight=sample_weights,
              eval_set=[(X_val, y_val)], verbose=False)
    return model


def train_lgb(X_train, y_train, X_val, y_val, **kwargs):
    class_counts = np.bincount(y_train, minlength=3)
    sample_weights = np.array([len(y_train) / (3.0 * class_counts[c]) for c in y_train])
    params = dict(
        n_estimators=500, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
        reg_alpha=0.1, reg_lambda=1.0,
        objective="multiclass", num_class=3,
        metric="multi_logloss",
        random_state=42, n_jobs=-1, verbose=-1,
    )
    params.update(kwargs)
    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train, sample_weight=sample_weights,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
    )
    return model


def evaluate(model, X_test, y_test, label=""):
    preds = model.predict(X_test)
    acc = np.mean(preds == y_test)
    logger.info(f"  {label}: {acc:.4f} ({int(acc*len(y_test))}/{len(y_test)})")
    return acc


def main():
    logger.info("Loading data...")
    df = load_data()
    logger.info(f"Data: {len(df)} matches, {len(ALL_FEATURES)} features")

    # ==== Experiment 1: XGBoost vs LightGBM (full 20 features) ====
    logger.info("\n" + "="*60)
    logger.info("EXP 1: XGBoost vs LightGBM (20 features)")
    logger.info("="*60)
    X_train, y_train, X_val, y_val, X_test, y_test = split_data(df, ALL_FEATURES)
    logger.info(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    xgb_model = train_xgb(X_train, y_train, X_val, y_val)
    xgb_acc = evaluate(xgb_model, X_test, y_test, "XGBoost")

    lgb_model = train_lgb(X_train, y_train, X_val, y_val)
    lgb_acc = evaluate(lgb_model, X_test, y_test, "LightGBM")

    # ==== Experiment 2: Feature selection (top features by importance) ====
    logger.info("\n" + "="*60)
    logger.info("EXP 2: Feature Selection")
    logger.info("="*60)

    importances = xgb_model.feature_importances_
    feature_imp = sorted(zip(ALL_FEATURES, importances), key=lambda x: x[1], reverse=True)
    logger.info("Feature importances:")
    for name, imp in feature_imp:
        logger.info(f"  {name}: {imp:.4f}")

    for top_n in [16, 14, 12, 10, 8]:
        top_features = [f for f, _ in feature_imp[:top_n]]
        X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, top_features)
        m = train_xgb(X_tr, y_tr, X_v, y_v)
        evaluate(m, X_te, y_te, f"XGB top-{top_n}")

    # ==== Experiment 3: LightGBM hyperparams ====
    logger.info("\n" + "="*60)
    logger.info("EXP 3: LightGBM hyperparameter variations")
    logger.info("="*60)
    X_train, y_train, X_val, y_val, X_test, y_test = split_data(df, ALL_FEATURES)

    configs = [
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 800, "num_leaves": 15},
        {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 500, "num_leaves": 20},
        {"max_depth": 6, "learning_rate": 0.05, "n_estimators": 500, "num_leaves": 40},
        {"max_depth": -1, "learning_rate": 0.03, "n_estimators": 1000, "num_leaves": 31},
        {"max_depth": 5, "learning_rate": 0.01, "n_estimators": 1500, "num_leaves": 31},
    ]
    for i, cfg in enumerate(configs):
        m = train_lgb(X_train, y_train, X_val, y_val, **cfg)
        evaluate(m, X_test, y_test, f"LGB cfg-{i+1} ({cfg})")

    # ==== Experiment 4: XGBoost hyperparams ====
    logger.info("\n" + "="*60)
    logger.info("EXP 4: XGBoost hyperparameter variations")
    logger.info("="*60)

    xgb_configs = [
        {"max_depth": 3, "learning_rate": 0.03, "n_estimators": 800},
        {"max_depth": 4, "learning_rate": 0.05, "n_estimators": 500},
        {"max_depth": 6, "learning_rate": 0.03, "n_estimators": 800},
        {"max_depth": 5, "learning_rate": 0.01, "n_estimators": 1500},
        {"max_depth": 7, "learning_rate": 0.05, "n_estimators": 500},
    ]
    for i, cfg in enumerate(xgb_configs):
        m = train_xgb(X_train, y_train, X_val, y_val, **cfg)
        evaluate(m, X_test, y_test, f"XGB cfg-{i+1} ({cfg})")

    # ==== Experiment 5: Larger test set ====
    logger.info("\n" + "="*60)
    logger.info("EXP 5: Larger test set (10%) for more robust evaluation")
    logger.info("="*60)
    X_train, y_train, X_val, y_val, X_test, y_test = split_data(df, ALL_FEATURES, test_pct=0.10, val_pct=0.10)
    logger.info(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    m_xgb = train_xgb(X_train, y_train, X_val, y_val)
    evaluate(m_xgb, X_test, y_test, "XGBoost (10% test)")

    m_lgb = train_lgb(X_train, y_train, X_val, y_val)
    evaluate(m_lgb, X_test, y_test, "LightGBM (10% test)")


if __name__ == "__main__":
    main()
