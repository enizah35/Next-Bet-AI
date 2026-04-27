"""
src/model/train.py
Entraînement — NN Ensemble + XGBoost + LightGBM + Stacking.
54 features combinant stats historiques, cotes, forme, xG proxy et signaux de marché.
"""

import json
import logging
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import MatchRaw, MatchFeature
from src.model.network import (
    MatchPredictor,
    DEFAULT_MODEL_CONFIG,
    LABEL_TO_INDEX,
)

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# ============================================================
# Chemins de sauvegarde
# ============================================================
MODEL_DIR: Path = Path(__file__).parent / "checkpoints"
MODEL_PATH: Path = MODEL_DIR / "match_predictor.pt"
SCALER_PATH: Path = MODEL_DIR / "scaler_params.json"
METRICS_PATH: Path = MODEL_DIR / "training_metrics.json"
XGBOOST_PATH: Path = MODEL_DIR / "xgboost_model.json"
LIGHTGBM_PATH: Path = MODEL_DIR / "lightgbm_model.txt"
META_MODEL_PATH: Path = MODEL_DIR / "meta_model.pkl"
DRAW_MODEL_PATH: Path = MODEL_DIR / "draw_model.txt"

# ============================================================
# Hyperparamètres
# ============================================================
TRAIN_CONFIG: dict = {
    "epochs": 300,
    "batch_size": 64,
    "learning_rate": 0.001,
    "weight_decay": 1e-3,
    "patience": 50,
    "val_split": 0.15,   # augmenté : plus de données pour le meta-learner
    "test_split": 0.10,  # augmenté : test set plus représentatif
    "random_state": 13,
    "ensemble_seeds": [13, 42, 99],
    "use_class_weights": False,  # False = optimise l'accuracy globale, True = reequilibre H/D/A
}

# ============================================================
# Features : DB + implied odds + interactions engineered
# ============================================================
FEATURE_COLUMNS: list[str] = [
    # Probabilités implicites du marché (3)
    "implied_home", "implied_draw", "implied_away",
    # Elo (3)
    "home_elo", "away_elo", "elo_diff",
    # Forme générale domicile (3)
    "home_pts_last_5", "home_goals_scored_last_5", "home_goals_conceded_last_5",
    # Forme générale extérieur (3)
    "away_pts_last_5", "away_goals_scored_last_5", "away_goals_conceded_last_5",
    # Forme spécifique terrain (2)
    "home_pts_last_5_at_home", "away_pts_last_5_away",
    # Tirs cadrés (4)
    "home_sot_last_5", "away_sot_last_5",
    "home_sot_conceded_last_5", "away_sot_conceded_last_5",
    # xG proxy (2)
    "home_xg_last_5", "away_xg_last_5",
    # Fatigue / repos (2)
    "home_days_rest", "away_days_rest",
    # Série & momentum (4)
    "home_unbeaten_streak", "away_unbeaten_streak",
    "home_momentum", "away_momentum",
    # Confrontations directes (2)
    "h2h_dominance", "h2h_avg_goals",
    # Features engineered (3)
    "form_pts_diff",   # home_pts_last_5 - away_pts_last_5
    "goal_diff_home",  # home_goals_scored_last_5 - home_goals_conceded_last_5
    "goal_diff_away",  # away_goals_scored_last_5 - away_goals_conceded_last_5
    # Marché sur/sous 2.5 buts (1)
    "implied_over25",  # Probabilité implicite over 2.5 buts (expectation de buts)
    # Mouvement de cotes B365 vs marché (2) — signal "smart money"
    "odds_mov_home",   # implied_home_closing (B365) - implied_home_opening (market)
    "odds_mov_draw",   # implied_draw_closing (B365) - implied_draw_opening (market)
    # Blessures pré-match API-Football Pro (3) — 0 si données indisponibles
    "home_injured_count",
    "away_injured_count",
    "injury_diff",     # away_injured - home_injured (avantage relatif)
    # Taux historiques par ligue (3) — signal de style de jeu inter-ligue
    "league_home_rate",  # % victoires domicile dans cette ligue (historique)
    "league_draw_rate",  # % matchs nuls dans cette ligue
    "league_away_rate",  # % victoires extérieur dans cette ligue
    "market_home_away_gap",
    "market_favorite_prob",
    "market_draw_gap",
    "market_entropy",
    "form_goal_diff",
    "xg_diff",
    "sot_diff",
    "sot_conceded_diff",
    "rest_diff",
    "momentum_diff",
    "unbeaten_diff",
    "home_attack_vs_away_defense",
    "away_attack_vs_home_defense",
    "attack_balance",
]
# Total : 54 features


def load_training_data(session: Session) -> pd.DataFrame:
    """Charge toutes les features depuis PostgreSQL + calcule les probabilités implicites."""
    stmt = (
        select(
            MatchFeature.match_id,
            # Forme générale
            MatchFeature.home_pts_last_5,
            MatchFeature.home_goals_scored_last_5,
            MatchFeature.home_goals_conceded_last_5,
            MatchFeature.away_pts_last_5,
            MatchFeature.away_goals_scored_last_5,
            MatchFeature.away_goals_conceded_last_5,
            # Elo
            MatchFeature.home_elo,
            MatchFeature.away_elo,
            MatchFeature.elo_diff,
            # Forme spécifique terrain
            MatchFeature.home_pts_last_5_at_home,
            MatchFeature.away_pts_last_5_away,
            # Repos
            MatchFeature.home_days_rest,
            MatchFeature.away_days_rest,
            # xG
            MatchFeature.home_xg_last_5,
            MatchFeature.away_xg_last_5,
            # Tirs cadrés
            MatchFeature.home_sot_last_5,
            MatchFeature.away_sot_last_5,
            MatchFeature.home_sot_conceded_last_5,
            MatchFeature.away_sot_conceded_last_5,
            # Streak & momentum
            MatchFeature.home_unbeaten_streak,
            MatchFeature.away_unbeaten_streak,
            MatchFeature.home_momentum,
            MatchFeature.away_momentum,
            # H2H
            MatchFeature.h2h_dominance,
            MatchFeature.h2h_avg_goals,
            # Blessures (API-Football Pro)
            MatchFeature.home_injured_count,
            MatchFeature.away_injured_count,
            # Cotes du marché (pour implied odds + over/under + mouvement)
            MatchRaw.avg_h,
            MatchRaw.avg_d,
            MatchRaw.avg_a,
            MatchRaw.avg_over_25,
            MatchRaw.avg_under_25,
            MatchRaw.b365_ch,
            MatchRaw.b365_cd,
            MatchRaw.b365_ca,
            # Division (pour calcul des taux par ligue)
            MatchRaw.div,
            # Target
            MatchRaw.ftr,
        )
        .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
        .order_by(MatchRaw.date)
    )

    rows = session.execute(stmt).fetchall()
    raw_columns = [
        "match_id",
        "home_pts_last_5", "home_goals_scored_last_5", "home_goals_conceded_last_5",
        "away_pts_last_5", "away_goals_scored_last_5", "away_goals_conceded_last_5",
        "home_elo", "away_elo", "elo_diff",
        "home_pts_last_5_at_home", "away_pts_last_5_away",
        "home_days_rest", "away_days_rest",
        "home_xg_last_5", "away_xg_last_5",
        "home_sot_last_5", "away_sot_last_5",
        "home_sot_conceded_last_5", "away_sot_conceded_last_5",
        "home_unbeaten_streak", "away_unbeaten_streak",
        "home_momentum", "away_momentum",
        "h2h_dominance", "h2h_avg_goals",
        "home_injured_count", "away_injured_count",
        "avg_h", "avg_d", "avg_a",
        "avg_over_25", "avg_under_25",
        "b365_ch", "b365_cd", "b365_ca",
        "div",
        "ftr",
    ]
    df: pd.DataFrame = pd.DataFrame(rows, columns=raw_columns)

    # Probabilités implicites : cotes bookmakers si disponibles, sinon calcul depuis Elo
    has_odds = df["avg_h"].notna() & df["avg_d"].notna() & df["avg_a"].notna()
    logger.info(f"Matchs avec cotes bookmakers : {has_odds.sum()} / {len(df)} total")

    df["implied_home"] = np.nan
    df["implied_draw"] = np.nan
    df["implied_away"] = np.nan

    # Cotes disponibles → implied odds avec suppression de la marge bookmaker
    if has_odds.any():
        margin = (1.0 / df.loc[has_odds, "avg_h"]
                  + 1.0 / df.loc[has_odds, "avg_d"]
                  + 1.0 / df.loc[has_odds, "avg_a"])
        df.loc[has_odds, "implied_home"] = (1.0 / df.loc[has_odds, "avg_h"]) / margin
        df.loc[has_odds, "implied_draw"] = (1.0 / df.loc[has_odds, "avg_d"]) / margin
        df.loc[has_odds, "implied_away"] = (1.0 / df.loc[has_odds, "avg_a"]) / margin

    # Cotes absentes → probabilités calculées depuis l'Elo (avantage domicile +60 pts)
    HOME_ADV_ELO = 60.0
    DRAW_RATE = 0.26  # taux moyen de nul en football européen
    no_odds = ~has_odds
    if no_odds.any():
        elo_h = df.loc[no_odds, "home_elo"].fillna(1500.0)
        elo_a = df.loc[no_odds, "away_elo"].fillna(1500.0)
        p_home_raw = 1.0 / (1.0 + 10.0 ** ((elo_a - elo_h - HOME_ADV_ELO) / 400.0))
        df.loc[no_odds, "implied_home"] = p_home_raw * (1.0 - DRAW_RATE)
        df.loc[no_odds, "implied_away"] = (1.0 - p_home_raw) * (1.0 - DRAW_RATE)
        df.loc[no_odds, "implied_draw"] = DRAW_RATE
        logger.info(f"{no_odds.sum()} matchs sans cotes → implied odds calculées depuis l'Elo")

    df = df.drop(columns=["avg_h", "avg_d", "avg_a"])

    # --- Implied over 2.5 buts ---
    over_valid = df["avg_over_25"].notna() & df["avg_under_25"].notna()
    df["implied_over25"] = 0.5  # neutre par défaut
    if over_valid.any():
        raw_over = 1.0 / df.loc[over_valid, "avg_over_25"]
        raw_under = 1.0 / df.loc[over_valid, "avg_under_25"]
        df.loc[over_valid, "implied_over25"] = raw_over / (raw_over + raw_under)
    df = df.drop(columns=["avg_over_25", "avg_under_25"])

    # --- Mouvement de cotes B365 closing vs marché opening (signal smart money) ---
    b365_valid = df["b365_ch"].notna() & df["b365_cd"].notna() & df["b365_ca"].notna()
    df["odds_mov_home"] = 0.0
    df["odds_mov_draw"] = 0.0
    if b365_valid.any():
        b365_margin = (1.0 / df.loc[b365_valid, "b365_ch"]
                       + 1.0 / df.loc[b365_valid, "b365_cd"]
                       + 1.0 / df.loc[b365_valid, "b365_ca"])
        implied_closing_home = (1.0 / df.loc[b365_valid, "b365_ch"]) / b365_margin
        implied_closing_draw = (1.0 / df.loc[b365_valid, "b365_cd"]) / b365_margin
        df.loc[b365_valid, "odds_mov_home"] = implied_closing_home - df.loc[b365_valid, "implied_home"]
        df.loc[b365_valid, "odds_mov_draw"] = implied_closing_draw - df.loc[b365_valid, "implied_draw"]
    df = df.drop(columns=["b365_ch", "b365_cd", "b365_ca"])

    # Imputation des NaN (premier match par équipe → pas de données historiques)
    df["home_days_rest"] = df["home_days_rest"].fillna(7.0)
    df["away_days_rest"] = df["away_days_rest"].fillna(7.0)
    df["home_unbeaten_streak"] = df["home_unbeaten_streak"].fillna(0.0)
    df["away_unbeaten_streak"] = df["away_unbeaten_streak"].fillna(0.0)
    df["home_momentum"] = df["home_momentum"].fillna(1.0)
    df["away_momentum"] = df["away_momentum"].fillna(1.0)
    df["h2h_dominance"] = df["h2h_dominance"].fillna(0.0)
    df["h2h_avg_goals"] = df["h2h_avg_goals"].fillna(2.5)

    # Blessures : 0 si données indisponibles (avant API-Football Pro)
    df["home_injured_count"] = pd.to_numeric(df["home_injured_count"], errors="coerce").fillna(0.0)
    df["away_injured_count"] = pd.to_numeric(df["away_injured_count"], errors="coerce").fillna(0.0)

    # Features engineered (interactions)
    df["form_pts_diff"] = df["home_pts_last_5"] - df["away_pts_last_5"]
    df["goal_diff_home"] = df["home_goals_scored_last_5"] - df["home_goals_conceded_last_5"]
    df["goal_diff_away"] = df["away_goals_scored_last_5"] - df["away_goals_conceded_last_5"]
    df["injury_diff"] = df["away_injured_count"] - df["home_injured_count"]
    market_probs = df[["implied_home", "implied_draw", "implied_away"]].clip(lower=1e-6, upper=1.0)
    df["market_home_away_gap"] = df["implied_home"] - df["implied_away"]
    df["market_favorite_prob"] = market_probs.max(axis=1)
    df["market_draw_gap"] = df["implied_draw"] - df[["implied_home", "implied_away"]].max(axis=1)
    df["market_entropy"] = -(market_probs * np.log(market_probs)).sum(axis=1)
    df["form_goal_diff"] = df["goal_diff_home"] - df["goal_diff_away"]
    df["xg_diff"] = df["home_xg_last_5"] - df["away_xg_last_5"]
    df["sot_diff"] = df["home_sot_last_5"] - df["away_sot_last_5"]
    df["sot_conceded_diff"] = df["home_sot_conceded_last_5"] - df["away_sot_conceded_last_5"]
    df["rest_diff"] = df["home_days_rest"] - df["away_days_rest"]
    df["momentum_diff"] = df["home_momentum"] - df["away_momentum"]
    df["unbeaten_diff"] = df["home_unbeaten_streak"] - df["away_unbeaten_streak"]
    df["home_attack_vs_away_defense"] = df["home_goals_scored_last_5"] - df["away_goals_conceded_last_5"]
    df["away_attack_vs_home_defense"] = df["away_goals_scored_last_5"] - df["home_goals_conceded_last_5"]
    df["attack_balance"] = df["home_attack_vs_away_defense"] - df["away_attack_vs_home_defense"]

    # Taux historiques par ligue — calculés sur l'ensemble du dataset (connaissance a priori stable)
    # Ces taux encodent le style de jeu propre à chaque championnat (home advantage, fréquence des nuls…)
    league_rates = df.groupby("div")["ftr"].agg(
        league_home_rate=lambda s: float((s == "H").mean()),
        league_draw_rate=lambda s: float((s == "D").mean()),
        league_away_rate=lambda s: float((s == "A").mean()),
    ).reset_index()
    df = df.merge(league_rates, on="div", how="left")

    # Fallback si div manquant (ne devrait pas arriver)
    df["league_home_rate"] = df["league_home_rate"].fillna(0.46)
    df["league_draw_rate"] = df["league_draw_rate"].fillna(0.26)
    df["league_away_rate"] = df["league_away_rate"].fillna(0.28)

    logger.info(
        f"Données chargées : {len(df)} matchs, {len(FEATURE_COLUMNS)} features | "
        f"Ligues : {df['div'].value_counts().to_dict()}"
    )
    return df


def prepare_datasets(df: pd.DataFrame) -> tuple:
    """Prépare train/val/test — split chronologique, StandardScaler, tensors PyTorch."""
    df_clean: pd.DataFrame = df[df["ftr"].isin(LABEL_TO_INDEX)].copy()
    removed_targets = len(df) - len(df_clean)
    if removed_targets:
        logger.info(f"Matchs sans target valide ignores : {removed_targets}")

    feature_frame = (
        df_clean[FEATURE_COLUMNS]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
    )
    rows_with_nan = int(feature_frame.isna().any(axis=1).sum())
    total_nan = int(feature_frame.isna().sum().sum())
    logger.info(
        "Features NaN avant imputation : "
        f"{rows_with_nan} matchs / {len(df_clean)} ({total_nan} valeurs)"
    )

    y: np.ndarray = df_clean["ftr"].map(LABEL_TO_INDEX).values.astype(np.int64)

    unique, counts = np.unique(y, return_counts=True)
    dist = {int(u): int(c) for u, c in zip(unique, counts)}
    logger.info(f"Classes — H:{dist.get(0,0)}, D:{dist.get(1,0)}, A:{dist.get(2,0)}")

    n_total = len(df_clean)
    n_test = int(n_total * TRAIN_CONFIG["test_split"])
    n_val = int(n_total * TRAIN_CONFIG["val_split"])
    n_train = n_total - n_val - n_test

    train_features = feature_frame.iloc[:n_train].copy()
    val_features = feature_frame.iloc[n_train:n_train + n_val].copy()
    test_features = feature_frame.iloc[n_train + n_val:].copy()

    imputation_values = train_features.median(numeric_only=True).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    X_train_raw = train_features.fillna(imputation_values).values.astype(np.float32)
    X_val_raw = val_features.fillna(imputation_values).values.astype(np.float32)
    X_test_raw = test_features.fillna(imputation_values).values.astype(np.float32)

    y_train = y[:n_train]
    y_val = y[n_train:n_train + n_val]
    y_test = y[n_train + n_val:]

    logger.info(f"Split — Train: {n_train}, Val: {n_val}, Test: {n_test}")

    market_train_preds = X_train_raw[:, :3].argmax(axis=1)
    market_val_preds = X_val_raw[:, :3].argmax(axis=1)
    market_test_preds = X_test_raw[:, :3].argmax(axis=1)
    market_full_preds = np.concatenate([market_train_preds, market_val_preds, market_test_preds])
    market_test_accuracy = float(np.mean(market_test_preds == y_test))
    market_full_accuracy = float(np.mean(market_full_preds == y))
    logger.info(
        f"Baseline marche favori — Test Acc: {market_test_accuracy:.3f} | "
        f"Full Acc: {market_full_accuracy:.3f}"
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train_raw).astype(np.float32)
    X_val = scaler.transform(X_val_raw).astype(np.float32)
    X_test = scaler.transform(X_test_raw).astype(np.float32)

    scaler_params = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "feature_columns": FEATURE_COLUMNS,
        "imputation_values": {col: float(imputation_values[col]) for col in FEATURE_COLUMNS},
    }

    class_weights = None
    if TRAIN_CONFIG["use_class_weights"]:
        class_counts = np.bincount(y_train, minlength=3)
        class_weights = torch.tensor(
            n_train / (3.0 * class_counts + 1e-8), dtype=torch.float32
        )
        logger.info(
            f"Poids classes : H={class_weights[0]:.2f}, "
            f"D={class_weights[1]:.2f}, A={class_weights[2]:.2f}"
        )
    else:
        logger.info("Poids classes desactives : optimisation accuracy globale.")

    train_dataset = TensorDataset(torch.tensor(X_train), torch.tensor(y_train))
    val_dataset = TensorDataset(torch.tensor(X_val), torch.tensor(y_val))
    test_dataset = TensorDataset(torch.tensor(X_test), torch.tensor(y_test))

    numpy_splits = {
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "X_test": X_test, "y_test": y_test,
        "X_train_raw": X_train_raw,
        "X_val_raw": X_val_raw,
        "X_test_raw": X_test_raw,
        "market_test_accuracy": market_test_accuracy,
        "market_full_accuracy": market_full_accuracy,
        "rows_with_feature_nan": rows_with_nan,
        "total_feature_nan": total_nan,
    }
    return train_dataset, val_dataset, test_dataset, scaler_params, class_weights, numpy_splits


def train_model(
    train_dataset: TensorDataset,
    val_dataset: TensorDataset,
    class_weights: torch.Tensor | None,
    model_config: dict,
) -> tuple[MatchPredictor, dict]:
    """Entraîne un NN avec early stopping."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_loader = DataLoader(train_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=False)

    model: MatchPredictor = MatchPredictor(**model_config).to(device)
    logger.info(f"Paramètres NN : {sum(p.numel() for p in model.parameters()):,}")

    weight_tensor = class_weights.to(device) if class_weights is not None else None
    criterion = nn.CrossEntropyLoss(weight=weight_tensor)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=TRAIN_CONFIG["learning_rate"],
        weight_decay=TRAIN_CONFIG["weight_decay"],
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=15, min_lr=1e-5
    )

    best_val_loss = float("inf")
    best_val_acc = 0.0
    patience_counter = 0
    best_state = None

    for epoch in range(1, TRAIN_CONFIG["epochs"] + 1):
        model.train()
        train_loss_sum = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            loss = criterion(model(X_batch), y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss_sum += loss.item()

        model.eval()
        val_loss_sum, val_correct, val_total = 0.0, 0, 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                logits = model(X_batch)
                val_loss_sum += criterion(logits, y_batch).item()
                val_correct += (logits.argmax(dim=-1) == y_batch).sum().item()
                val_total += y_batch.size(0)

        avg_val_loss = val_loss_sum / max(len(val_loader), 1)
        val_acc = val_correct / max(val_total, 1)
        scheduler.step(avg_val_loss)

        if epoch % 10 == 0 or epoch == 1:
            logger.info(
                f"Epoch {epoch:03d} | Train: {train_loss_sum/len(train_loader):.4f} | "
                f"Val: {avg_val_loss:.4f} | Acc: {val_acc:.3f} | LR: {optimizer.param_groups[0]['lr']:.2e}"
            )

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_val_acc = val_acc
            patience_counter = 0
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= TRAIN_CONFIG["patience"]:
                logger.info(f"Early stopping à l'epoch {epoch}")
                break

    model.load_state_dict(best_state)
    model.to(device)
    return model, {
        "best_val_loss": round(best_val_loss, 4),
        "best_val_acc": round(best_val_acc, 4),
        "epochs_trained": epoch,
        "model_config": model_config,
    }


def calibrate_temperature(model: MatchPredictor, val_dataset: TensorDataset) -> float:
    """Temperature scaling sur le jeu de validation."""
    device = next(model.parameters()).device
    all_logits, all_labels = [], []
    model.eval()
    with torch.no_grad():
        for X_batch, y_batch in DataLoader(val_dataset, batch_size=256):
            all_logits.append(model(X_batch.to(device)).cpu())
            all_labels.append(y_batch)

    logits_cat = torch.cat(all_logits)
    labels_cat = torch.cat(all_labels)

    best_temp, best_nll = 1.0, float("inf")
    for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0, 2.5, 3.0]:
        nll = nn.CrossEntropyLoss()(logits_cat / t, labels_cat).item()
        if nll < best_nll:
            best_nll, best_temp = nll, t

    logger.info(f"Temperature optimale : T={best_temp:.2f} (NLL={best_nll:.4f})")
    return best_temp


def get_nn_probs(models: list[MatchPredictor], X: np.ndarray, temperature: float) -> np.ndarray:
    """Probabilités softmax moyennées de l'ensemble NN."""
    device = next(models[0].parameters()).device
    x_tensor = torch.tensor(X, dtype=torch.float32).to(device)
    avg_probs = torch.zeros(len(X), 3, device=device)
    with torch.no_grad():
        for m in models:
            m.eval()
            avg_probs += torch.softmax(m(x_tensor) / temperature, dim=-1)
    avg_probs /= len(models)
    return avg_probs.cpu().numpy()


def train_xgboost(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    use_class_weights: bool = False,
) -> xgb.XGBClassifier:
    """Entraîne XGBoost multiclass."""
    fit_kwargs = {}
    if use_class_weights:
        class_counts = np.bincount(y_train, minlength=3)
        fit_kwargs["sample_weight"] = np.array([len(y_train) / (3.0 * class_counts[c]) for c in y_train])

    model = xgb.XGBClassifier(
        n_estimators=1000,
        max_depth=5,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        early_stopping_rounds=50,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
        **fit_kwargs,
    )
    logger.info(f"XGBoost — best iter: {model.best_iteration}, score: {model.best_score:.4f}")
    return model


def train_lightgbm(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    use_class_weights: bool = False,
) -> lgb.LGBMClassifier:
    """Entraîne LightGBM multiclass."""
    fit_kwargs = {}
    if use_class_weights:
        class_counts = np.bincount(y_train, minlength=3)
        fit_kwargs["sample_weight"] = np.array([len(y_train) / (3.0 * class_counts[c]) for c in y_train])

    model = lgb.LGBMClassifier(
        n_estimators=1000,
        max_depth=6,
        learning_rate=0.03,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_samples=20,
        reg_alpha=0.1,
        reg_lambda=1.0,
        objective="multiclass",
        num_class=3,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)],
        **fit_kwargs,
    )
    best_iter = model.best_iteration_ if hasattr(model, "best_iteration_") else "?"
    logger.info(f"LightGBM — best iter: {best_iter}")
    return model


def train_draw_specialist(
    X_train: np.ndarray, y_train: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
) -> lgb.LGBMClassifier:
    """Entraîne un modèle binaire spécialisé nul vs non-nul."""
    y_train_draw = (y_train == LABEL_TO_INDEX["D"]).astype(np.int64)
    y_val_draw = (y_val == LABEL_TO_INDEX["D"]).astype(np.int64)

    model = lgb.LGBMClassifier(
        n_estimators=600,
        max_depth=4,
        learning_rate=0.025,
        num_leaves=31,
        subsample=0.85,
        colsample_bytree=0.85,
        min_child_samples=25,
        reg_alpha=0.2,
        reg_lambda=1.2,
        objective="binary",
        class_weight="balanced",
        random_state=43,
        n_jobs=-1,
        verbose=-1,
    )
    model.fit(
        X_train,
        y_train_draw,
        eval_set=[(X_val, y_val_draw)],
        eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(period=-1)],
    )
    best_iter = model.best_iteration_ if hasattr(model, "best_iteration_") else "?"
    logger.info(f"Draw specialist — best iter: {best_iter}")
    return model


def evaluate_draw_specialist(draw_model: lgb.LGBMClassifier, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """Mesures simples pour savoir si le modèle de nuls apporte un signal."""
    y_draw = (y_test == LABEL_TO_INDEX["D"]).astype(np.int64)
    probs = draw_model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.50).astype(np.int64)
    selected = int(preds.sum())
    hits = int(((preds == 1) & (y_draw == 1)).sum())
    precision = hits / max(selected, 1)
    recall = hits / max(int(y_draw.sum()), 1)
    logger.info(
        f"Draw specialist — selected={selected}, precision={precision:.3f}, recall={recall:.3f}"
    )
    return {
        "selected": selected,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def build_meta_features(
    nn_probs: np.ndarray,
    xgb_probs: np.ndarray,
    lgb_probs: np.ndarray,
    X_raw: np.ndarray,
) -> np.ndarray:
    """
    Meta-features pour le stacking :
    9 probabilités (NN + XGB + LGB) + 3 cotes implicites (indices 0-2 dans X_raw).
    """
    implied_odds = X_raw[:, :3]  # implied_home, implied_draw, implied_away (colonnes 0-2)
    return np.hstack([nn_probs, xgb_probs, lgb_probs, implied_odds])


def evaluate_ensemble(
    models: list[MatchPredictor], test_dataset: TensorDataset, temperature: float
) -> dict:
    """Évalue l'ensemble NN sur le jeu de test."""
    device = next(models[0].parameters()).device
    correct, total = 0, 0
    class_correct = {0: 0, 1: 0, 2: 0}
    class_total = {0: 0, 1: 0, 2: 0}

    with torch.no_grad():
        for X_batch, y_batch in DataLoader(test_dataset, batch_size=256):
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            avg_probs = torch.zeros(X_batch.size(0), 3, device=device)
            for m in models:
                m.eval()
                avg_probs += torch.softmax(m(X_batch) / temperature, dim=-1)
            avg_probs /= len(models)
            preds = avg_probs.argmax(dim=-1)
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)
            for cls in range(3):
                mask = y_batch == cls
                class_correct[cls] += (preds[mask] == cls).sum().item()
                class_total[cls] += mask.sum().item()

    test_acc = correct / max(total, 1)
    per_class = {
        "H": round(class_correct[0] / max(class_total[0], 1), 3),
        "D": round(class_correct[1] / max(class_total[1], 1), 3),
        "A": round(class_correct[2] / max(class_total[2], 1), 3),
    }
    logger.info(f"NN Ensemble — Test Acc: {test_acc:.3f} | {per_class}")
    return {"test_accuracy": round(test_acc, 4), "per_class_accuracy": per_class, "test_samples": total}


def evaluate_confidence_bands(probs: np.ndarray, y_true: np.ndarray) -> dict:
    """
    Diagnostic secondaire: montre si la calibration progresse par niveau de confiance.
    L'objectif principal reste `test_accuracy` global sur tous les matchs.
    """
    preds = probs.argmax(axis=1)
    confidence = probs.max(axis=1)
    bands = {}

    for threshold in [0.50, 0.55, 0.60, 0.65, 0.70]:
        mask = confidence >= threshold
        selected = int(mask.sum())
        if selected == 0:
            bands[str(threshold)] = {"selected": 0, "coverage": 0.0, "accuracy": None}
            continue
        acc = float(np.mean(preds[mask] == y_true[mask]))
        bands[str(threshold)] = {
            "selected": selected,
            "coverage": round(selected / max(len(y_true), 1), 4),
            "accuracy": round(acc, 4),
        }

    return bands


def run_training(
    league_code: str | None = None,
    output_dir: Path | str | None = None,
    min_matches: int = 1000,
    source_df: pd.DataFrame | None = None,
) -> bool:
    """Point d'entrée principal : NN Ensemble + XGBoost + LightGBM + Stacking."""
    artifact_dir = Path(output_dir) if output_dir is not None else MODEL_DIR
    model_path = artifact_dir / MODEL_PATH.name
    scaler_path = artifact_dir / SCALER_PATH.name
    metrics_path = artifact_dir / METRICS_PATH.name
    xgboost_path = artifact_dir / XGBOOST_PATH.name
    lightgbm_path = artifact_dir / LIGHTGBM_PATH.name
    meta_model_path = artifact_dir / META_MODEL_PATH.name
    draw_model_path = artifact_dir / DRAW_MODEL_PATH.name
    run_label = f"LIGUE {league_code}" if league_code else "GLOBAL"

    logger.info("=" * 60)
    logger.info(f"ENTRAÎNEMENT {run_label} : NN + XGBoost + LightGBM + Stacking (54 features)")
    logger.info("=" * 60)

    artifact_dir.mkdir(parents=True, exist_ok=True)
    session: Session | None = None

    try:
        # 1. Données
        if source_df is None:
            session = get_session()
            df = load_training_data(session)
        else:
            df = source_df.copy()

        if league_code:
            df = df[df["div"] == league_code].copy()
            logger.info(f"Filtre ligue {league_code} : {len(df)} matchs")

        if df.empty:
            logger.error("Aucune donnée trouvée.")
            return False
        if len(df) < min_matches:
            logger.error(f"Données insuffisantes pour {run_label}: {len(df)} < {min_matches}")
            return False

        # 2. Datasets
        train_dataset, val_dataset, test_dataset, scaler_params, class_weights, splits = prepare_datasets(df)
        X_train, y_train = splits["X_train"], splits["y_train"]
        X_val, y_val = splits["X_val"], splits["y_val"]
        X_test, y_test = splits["X_test"], splits["y_test"]
        X_val_raw, X_test_raw = splits["X_val_raw"], splits["X_test_raw"]
        market_test_accuracy = splits["market_test_accuracy"]
        model_config = {**DEFAULT_MODEL_CONFIG, "input_dim": len(FEATURE_COLUMNS)}

        # ============================================================
        # 3. NN Ensemble
        # ============================================================
        models: list[MatchPredictor] = []
        all_train_metrics: list[dict] = []
        for i, seed in enumerate(TRAIN_CONFIG["ensemble_seeds"]):
            logger.info(f"\n{'='*40} NN {i+1}/{len(TRAIN_CONFIG['ensemble_seeds'])} (seed={seed}) {'='*40}")
            torch.manual_seed(seed)
            np.random.seed(seed)
            model, metrics = train_model(train_dataset, val_dataset, class_weights, model_config)
            models.append(model)
            all_train_metrics.append(metrics)

        best_idx = min(range(len(all_train_metrics)), key=lambda i: all_train_metrics[i]["best_val_loss"])
        temperature = calibrate_temperature(models[best_idx], val_dataset)
        nn_test_metrics = evaluate_ensemble(models, test_dataset, temperature)

        # ============================================================
        # 4. XGBoost
        # ============================================================
        logger.info(f"\n{'='*40} XGBoost {'='*40}")
        xgb_model = train_xgboost(
            X_train, y_train, X_val, y_val,
            use_class_weights=TRAIN_CONFIG["use_class_weights"],
        )
        xgb_test_preds = xgb_model.predict(X_test)
        xgb_test_acc = float(np.mean(xgb_test_preds == y_test))
        logger.info(f"XGBoost seul — Test Acc: {xgb_test_acc:.3f}")

        # ============================================================
        # 5. LightGBM
        # ============================================================
        logger.info(f"\n{'='*40} LightGBM {'='*40}")
        lgb_model = train_lightgbm(
            X_train, y_train, X_val, y_val,
            use_class_weights=TRAIN_CONFIG["use_class_weights"],
        )
        lgb_test_preds = lgb_model.predict(X_test)
        lgb_test_acc = float(np.mean(lgb_test_preds == y_test))
        logger.info(f"LightGBM seul — Test Acc: {lgb_test_acc:.3f}")

        # ============================================================
        # 5b. Draw specialist — binaire nul / non-nul
        # ============================================================
        logger.info(f"\n{'='*40} DRAW SPECIALIST {'='*40}")
        draw_model = train_draw_specialist(X_train, y_train, X_val, y_val)
        draw_metrics = evaluate_draw_specialist(draw_model, X_test, y_test)

        # ============================================================
        # 6. Stacking — méta-learner GradientBoosting
        # ============================================================
        logger.info(f"\n{'='*40} STACKING {'='*40}")

        nn_val_probs = get_nn_probs(models, X_val, temperature)
        xgb_val_probs = xgb_model.predict_proba(X_val)
        lgb_val_probs = lgb_model.predict_proba(X_val)
        meta_X_val = build_meta_features(nn_val_probs, xgb_val_probs, lgb_val_probs, X_val_raw)

        meta_model = GradientBoostingClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=10,
            random_state=42,
        )
        meta_model.fit(meta_X_val, y_val)

        nn_test_probs = get_nn_probs(models, X_test, temperature)
        xgb_test_probs = xgb_model.predict_proba(X_test)
        lgb_test_probs = lgb_model.predict_proba(X_test)
        meta_X_test = build_meta_features(nn_test_probs, xgb_test_probs, lgb_test_probs, X_test_raw)
        meta_test_preds = meta_model.predict(meta_X_test)
        meta_test_probs = meta_model.predict_proba(meta_X_test)
        meta_test_acc = float(np.mean(meta_test_preds == y_test))

        class_correct = {0: 0, 1: 0, 2: 0}
        class_total_cnt = {0: 0, 1: 0, 2: 0}
        for pred, true in zip(meta_test_preds, y_test):
            class_total_cnt[true] += 1
            if pred == true:
                class_correct[true] += 1
        per_class_acc = {
            "H": round(class_correct[0] / max(class_total_cnt[0], 1), 3),
            "D": round(class_correct[1] / max(class_total_cnt[1], 1), 3),
            "A": round(class_correct[2] / max(class_total_cnt[2], 1), 3),
        }
        logger.info(f"STACKING Test Acc : {meta_test_acc:.3f} | {per_class_acc}")

        confidence_metrics = {
            "nn_ensemble": evaluate_confidence_bands(nn_test_probs, y_test),
            "xgboost": evaluate_confidence_bands(xgb_test_probs, y_test),
            "lightgbm": evaluate_confidence_bands(lgb_test_probs, y_test),
            "stacking": evaluate_confidence_bands(meta_test_probs, y_test),
        }

        # ============================================================
        # 7. Meilleur modèle
        # ============================================================
        results = {
            "nn_ensemble": nn_test_metrics["test_accuracy"],
            "xgboost": round(xgb_test_acc, 4),
            "lightgbm": round(lgb_test_acc, 4),
            "stacking": round(meta_test_acc, 4),
        }
        best_approach = max(results, key=results.get)
        market_delta = round(results[best_approach] - market_test_accuracy, 4)
        best_confidence_metrics = confidence_metrics[best_approach]
        logger.info(f"\nRésultats : NN={results['nn_ensemble']:.3f}, XGB={results['xgboost']:.3f}, "
                    f"LGB={results['lightgbm']:.3f}, Stack={results['stacking']:.3f}")
        logger.info(f"Baseline marche favori : {market_test_accuracy:.3f} | Delta Best: {market_delta:+.3f}")
        logger.info(f"Meilleur : {best_approach} ({results[best_approach]:.3f})")
        logger.info(f"Diagnostic confiance >=60% : {best_confidence_metrics.get('0.6')}")

        # ============================================================
        # 8. Sauvegarde
        # ============================================================
        ensemble_state = {
            "num_models": len(models),
            "model_config": model_config,
            "scaler_params": scaler_params,
            "temperature": temperature,
            "best_approach": best_approach,
            "results": results,
            "league_code": league_code,
            "market_baseline_test_accuracy": round(market_test_accuracy, 4),
        }
        for i, m in enumerate(models):
            ensemble_state[f"model_{i}_state_dict"] = m.state_dict()

        torch.save(ensemble_state, model_path)
        xgb_model.save_model(str(xgboost_path))
        lgb_model.booster_.save_model(str(lightgbm_path))
        draw_model.booster_.save_model(str(draw_model_path))

        with open(meta_model_path, "wb") as f:
            pickle.dump(meta_model, f)

        with open(scaler_path, "w") as f:
            json.dump(scaler_params, f, indent=2)

        best_metrics = all_train_metrics[best_idx]
        all_metrics = {
            **best_metrics,
            "test_accuracy": results[best_approach],
            "per_class_accuracy": per_class_acc,
            "test_samples": len(y_test),
            "ensemble_size": len(models),
            "temperature": temperature,
            "best_approach": best_approach,
            "all_results": results,
            "market_baseline_test_accuracy": round(market_test_accuracy, 4),
            "market_baseline_full_accuracy": round(splits["market_full_accuracy"], 4),
            "best_vs_market_delta": round(results[best_approach] - market_test_accuracy, 4),
            "draw_specialist": draw_metrics,
            "rows_with_feature_nan": splits["rows_with_feature_nan"],
            "total_feature_nan": splits["total_feature_nan"],
            "use_class_weights": TRAIN_CONFIG["use_class_weights"],
            "league_code": league_code,
            "artifact_dir": str(artifact_dir),
            "confidence_bands": confidence_metrics,
            "best_confidence_bands": best_confidence_metrics,
            "num_features": len(FEATURE_COLUMNS),
        }
        with open(metrics_path, "w") as f:
            json.dump(all_metrics, f, indent=2)

        logger.info("=" * 60)
        logger.info("ENTRAÎNEMENT TERMINÉ")
        logger.info(f"  NN Ensemble : {results['nn_ensemble']:.3f}")
        logger.info(f"  XGBoost     : {results['xgboost']:.3f}")
        logger.info(f"  LightGBM    : {results['lightgbm']:.3f}")
        logger.info(f"  Stacking    : {results['stacking']:.3f}")
        logger.info(f"  Best        : {best_approach} ({results[best_approach]:.3f})")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale : {e}", exc_info=True)
        return False
    finally:
        if session:
            session.close()


def _normalize_cli_league(value: str) -> str:
    """Accepte un code football-data (F1) ou un nom de ligue (Ligue 1)."""
    from src.ingestion.load_historical import LEAGUE_NAMES

    raw = value.strip()
    upper = raw.upper()
    if upper in LEAGUE_NAMES:
        return upper

    aliases = {name.lower(): code for code, name in LEAGUE_NAMES.items()}
    code = aliases.get(raw.lower())
    if not code:
        valid = ", ".join([f"{code}={name}" for code, name in LEAGUE_NAMES.items()])
        raise ValueError(f"Ligue inconnue '{value}'. Valeurs possibles : {valid}")
    return code


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Entraine le modele global ou un modele specialise par ligue.")
    parser.add_argument("--league", help="Code football-data ou nom de ligue, ex: F1, E0, Ligue 1, Premier League")
    parser.add_argument("--output-dir", help="Dossier de sortie des checkpoints")
    parser.add_argument("--min-matches", type=int, default=1000, help="Minimum de matchs requis pour entrainer")
    args = parser.parse_args()

    league = _normalize_cli_league(args.league) if args.league else None
    default_output = MODEL_DIR / "leagues" / league if league else MODEL_DIR
    run_training(
        league_code=league,
        output_dir=Path(args.output_dir) if args.output_dir else default_output,
        min_matches=args.min_matches,
    )
