"""
src/model/train.py
Script d'entraînement — NN Ensemble + XGBoost stacking.
Charge les données depuis PostgreSQL, entraîne les modèles, et sauvegarde le checkpoint.
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
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

# ============================================================
# Hyperparamètres d'entraînement
# ============================================================
TRAIN_CONFIG: dict = {
    "epochs": 300,
    "batch_size": 64,
    "learning_rate": 0.001,
    "weight_decay": 1e-3,
    "patience": 50,
    "val_split": 0.1,
    "test_split": 0.05,
    "random_state": 13,
    "ensemble_seeds": [13, 42, 99],
}

# Colonnes features utilisées pour l'entraînement (14 features, sélection par importance XGBoost)
FEATURE_COLUMNS: list[str] = [
    # Probabilités implicites du marché (3)
    "implied_away",
    "implied_home",
    "implied_draw",
    # Elo (3)
    "away_elo",
    "elo_diff",
    "home_elo",
    # Forme (3)
    "home_goals_conceded_last_5",
    "away_goals_scored_last_5",
    "away_pts_last_5",
    # Forme spécifique dom/ext (2)
    "home_pts_last_5_at_home",
    "away_pts_last_5_away",
    # Tirs cadrés (3)
    "away_sot_last_5",
    "home_sot_last_5",
    "away_sot_conceded_last_5",
]


def load_training_data(session: Session) -> pd.DataFrame:
    """Charge les features et cotes depuis PostgreSQL, calcule les probabilités implicites."""
    stmt = (
        select(
            MatchFeature.match_id,
            # Probabilités implicites (calculées à partir des cotes)
            # → ajoutées ci-dessous après calcul
            # Elo
            MatchFeature.away_elo,
            MatchFeature.elo_diff,
            MatchFeature.home_elo,
            # Forme
            MatchFeature.home_goals_conceded_last_5,
            MatchFeature.away_goals_scored_last_5,
            MatchFeature.away_pts_last_5,
            # Forme spécifique
            MatchFeature.home_pts_last_5_at_home,
            MatchFeature.away_pts_last_5_away,
            # Tirs cadrés
            MatchFeature.away_sot_last_5,
            MatchFeature.home_sot_last_5,
            MatchFeature.away_sot_conceded_last_5,
            # Cotes du marché
            MatchRaw.avg_h,
            MatchRaw.avg_d,
            MatchRaw.avg_a,
            # Target
            MatchRaw.ftr,
        )
        .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
        .order_by(MatchRaw.date)
    )

    result = session.execute(stmt)
    rows = result.fetchall()

    raw_columns = [
        "match_id",
        "away_elo", "elo_diff", "home_elo",
        "home_goals_conceded_last_5", "away_goals_scored_last_5", "away_pts_last_5",
        "home_pts_last_5_at_home", "away_pts_last_5_away",
        "away_sot_last_5", "home_sot_last_5", "away_sot_conceded_last_5",
        "avg_h", "avg_d", "avg_a",
        "ftr",
    ]
    df: pd.DataFrame = pd.DataFrame(rows, columns=raw_columns)

    # --- Probabilités implicites : uniquement les cotes réelles ---
    df = df.dropna(subset=["avg_h", "avg_d", "avg_a"])
    logger.info(f"Matchs avec cotes bookmakers : {len(df)}")

    margin = (1.0 / df["avg_h"]) + (1.0 / df["avg_d"]) + (1.0 / df["avg_a"])
    df["implied_home"] = (1.0 / df["avg_h"]) / margin
    df["implied_draw"] = (1.0 / df["avg_d"]) / margin
    df["implied_away"] = (1.0 / df["avg_a"]) / margin

    df = df.drop(columns=["avg_h", "avg_d", "avg_a"])

    logger.info(f"Données chargées : {len(df)} matchs avec {len(FEATURE_COLUMNS)} features")
    return df


def prepare_datasets(df: pd.DataFrame) -> tuple:
    """
    Prépare les datasets train/val/test.
    Applique StandardScaler et convertit en tensors PyTorch.
    """
    # Suppression des lignes avec des NaN dans les features
    df_clean: pd.DataFrame = df.dropna(subset=FEATURE_COLUMNS)
    logger.info(f"Matchs après suppression NaN : {len(df_clean)} (supprimés : {len(df) - len(df_clean)})")

    # Séparation features / target
    X: np.ndarray = df_clean[FEATURE_COLUMNS].values.astype(np.float32)
    y: np.ndarray = df_clean["ftr"].map(LABEL_TO_INDEX).values.astype(np.int64)

    # Distribution des classes
    unique, counts = np.unique(y, return_counts=True)
    dist: dict = {int(u): int(c) for u, c in zip(unique, counts)}
    logger.info(f"Distribution des classes — H:{dist.get(0,0)}, D:{dist.get(1,0)}, A:{dist.get(2,0)}")

    # Split chronologique : on garde l'ordre temporel (pas de shuffle)
    n_total: int = len(X)
    n_test: int = int(n_total * TRAIN_CONFIG["test_split"])
    n_val: int = int(n_total * TRAIN_CONFIG["val_split"])
    n_train: int = n_total - n_val - n_test

    X_train, y_train = X[:n_train], y[:n_train]
    X_val, y_val = X[n_train:n_train + n_val], y[n_train:n_train + n_val]
    X_test, y_test = X[n_train + n_val:], y[n_train + n_val:]

    logger.info(f"Split — Train: {n_train}, Val: {n_val}, Test: {n_test}")

    # Normalisation (fit sur train uniquement)
    scaler: StandardScaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    # Sauvegarde des paramètres du scaler
    scaler_params: dict = {
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "feature_columns": FEATURE_COLUMNS,
    }

    # Calcul des poids de classe pour gérer le déséquilibre
    class_counts: np.ndarray = np.bincount(y_train, minlength=3)
    class_weights: torch.Tensor = torch.tensor(
        n_train / (3.0 * class_counts + 1e-8), dtype=torch.float32
    )
    logger.info(f"Poids des classes : H={class_weights[0]:.2f}, D={class_weights[1]:.2f}, A={class_weights[2]:.2f}")

    # Conversion en tensors PyTorch
    train_dataset = TensorDataset(torch.tensor(X_train), torch.tensor(y_train))
    val_dataset = TensorDataset(torch.tensor(X_val), torch.tensor(y_val))
    test_dataset = TensorDataset(torch.tensor(X_test), torch.tensor(y_test))

    # Retour : datasets PyTorch + arrays numpy bruts pour XGBoost
    numpy_splits = {
        "X_train": X_train, "y_train": y_train,
        "X_val": X_val, "y_val": y_val,
        "X_test": X_test, "y_test": y_test,
    }

    return train_dataset, val_dataset, test_dataset, scaler_params, class_weights, numpy_splits


def train_model(
    train_dataset: TensorDataset,
    val_dataset: TensorDataset,
    class_weights: torch.Tensor,
) -> tuple[MatchPredictor, dict]:
    """Entraîne le modèle avec early stopping."""

    device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Device d'entraînement : {device}")

    # DataLoaders
    train_loader = DataLoader(train_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=False)

    # Modèle
    model: MatchPredictor = MatchPredictor(**DEFAULT_MODEL_CONFIG).to(device)
    logger.info(f"Paramètres du modèle : {sum(p.numel() for p in model.parameters()):,}")

    # Loss avec poids de classe pour équilibrer H/D/A (surtout les nuls)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))

    # Optimiseur + Scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=TRAIN_CONFIG["learning_rate"],
        weight_decay=TRAIN_CONFIG["weight_decay"],
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=15, min_lr=1e-5
    )

    # Tracking
    best_val_loss: float = float("inf")
    best_val_acc: float = 0.0
    patience_counter: int = 0
    history: dict = {"train_loss": [], "val_loss": [], "val_acc": []}

    # ============================================================
    # Boucle d'entraînement
    # ============================================================
    for epoch in range(1, TRAIN_CONFIG["epochs"] + 1):
        # --- Train ---
        model.train()
        train_loss_sum: float = 0.0
        train_batches: int = 0

        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)

            optimizer.zero_grad()
            logits: torch.Tensor = model(X_batch)
            loss: torch.Tensor = criterion(logits, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss_sum += loss.item()
            train_batches += 1

        avg_train_loss: float = train_loss_sum / max(train_batches, 1)

        # --- Validation ---
        model.eval()
        val_loss_sum: float = 0.0
        val_correct: int = 0
        val_total: int = 0

        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                logits = model(X_batch)
                loss = criterion(logits, y_batch)
                val_loss_sum += loss.item()
                preds: torch.Tensor = logits.argmax(dim=-1)
                val_correct += (preds == y_batch).sum().item()
                val_total += y_batch.size(0)

        avg_val_loss: float = val_loss_sum / max(len(val_loader), 1)
        val_acc: float = val_correct / max(val_total, 1)

        history["train_loss"].append(avg_train_loss)
        history["val_loss"].append(avg_val_loss)
        history["val_acc"].append(val_acc)

        scheduler.step(avg_val_loss)

        # Logging périodique
        if epoch % 10 == 0 or epoch == 1:
            lr: float = optimizer.param_groups[0]["lr"]
            logger.info(
                f"Epoch {epoch:03d}/{TRAIN_CONFIG['epochs']} | "
                f"Train Loss: {avg_train_loss:.4f} | "
                f"Val Loss: {avg_val_loss:.4f} | "
                f"Val Acc: {val_acc:.3f} | "
                f"LR: {lr:.6f}"
            )

        # Early stopping
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_val_acc = val_acc
            patience_counter = 0
            # Sauvegarde du meilleur modèle
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        else:
            patience_counter += 1
            if patience_counter >= TRAIN_CONFIG["patience"]:
                logger.info(f"Early stopping à l'epoch {epoch} (patience={TRAIN_CONFIG['patience']})")
                break

    # Restauration du meilleur modèle
    model.load_state_dict(best_state)
    model.to(device)

    metrics: dict = {
        "best_val_loss": round(best_val_loss, 4),
        "best_val_acc": round(best_val_acc, 4),
        "epochs_trained": epoch,
        "model_config": DEFAULT_MODEL_CONFIG,
        "train_config": TRAIN_CONFIG,
    }

    logger.info(f"Meilleur modèle — Val Loss: {best_val_loss:.4f}, Val Acc: {best_val_acc:.3f}")
    return model, metrics


def evaluate_model(model: MatchPredictor, test_dataset: TensorDataset) -> dict:
    """Évalue le modèle sur le jeu de test."""
    device: torch.device = next(model.parameters()).device
    test_loader = DataLoader(test_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=False)

    model.eval()
    correct: int = 0
    total: int = 0
    class_correct: dict[int, int] = {0: 0, 1: 0, 2: 0}
    class_total: dict[int, int] = {0: 0, 1: 0, 2: 0}

    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            preds: torch.Tensor = model(X_batch).argmax(dim=-1)
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)

            for cls in range(3):
                mask = y_batch == cls
                class_correct[cls] += (preds[mask] == cls).sum().item()
                class_total[cls] += mask.sum().item()

    test_acc: float = correct / max(total, 1)
    per_class_acc: dict[str, float] = {
        "H": round(class_correct[0] / max(class_total[0], 1), 3),
        "D": round(class_correct[1] / max(class_total[1], 1), 3),
        "A": round(class_correct[2] / max(class_total[2], 1), 3),
    }

    logger.info(f"Test Accuracy : {test_acc:.3f}")
    logger.info(f"Par classe — H: {per_class_acc['H']}, D: {per_class_acc['D']}, A: {per_class_acc['A']}")

    return {"test_accuracy": round(test_acc, 4), "per_class_accuracy": per_class_acc, "test_samples": total}


def calibrate_temperature(model: MatchPredictor, val_dataset: TensorDataset) -> float:
    """Optimise un paramètre de température sur le jeu de validation (Temperature Scaling)."""
    device: torch.device = next(model.parameters()).device
    val_loader = DataLoader(val_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=False)

    # Collecter tous les logits et labels du validation set
    all_logits: list[torch.Tensor] = []
    all_labels: list[torch.Tensor] = []

    model.eval()
    with torch.no_grad():
        for X_batch, y_batch in val_loader:
            X_batch = X_batch.to(device)
            logits = model(X_batch)
            all_logits.append(logits.cpu())
            all_labels.append(y_batch)

    logits_cat = torch.cat(all_logits)
    labels_cat = torch.cat(all_labels)

    # Optimisation du paramètre de température par recherche sur grille
    best_temp: float = 1.0
    best_nll: float = float("inf")

    for t in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5, 1.7, 2.0, 2.5, 3.0]:
        scaled_logits = logits_cat / t
        nll = nn.CrossEntropyLoss()(scaled_logits, labels_cat).item()
        if nll < best_nll:
            best_nll = nll
            best_temp = t

    logger.info(f"Temperature scaling optimale : T={best_temp:.2f} (NLL={best_nll:.4f})")
    return best_temp


XGBOOST_PATH: Path = MODEL_DIR / "xgboost_model.json"
META_MODEL_PATH: Path = MODEL_DIR / "meta_model.pkl"


def train_xgboost(X_train: np.ndarray, y_train: np.ndarray,
                   X_val: np.ndarray, y_val: np.ndarray) -> xgb.XGBClassifier:
    """Entraîne un modèle XGBoost multiclass optimisé pour football."""
    # Poids de classes
    class_counts = np.bincount(y_train, minlength=3)
    sample_weights = np.array([len(y_train) / (3.0 * class_counts[c]) for c in y_train])

    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.05,
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
        sample_weight=sample_weights,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    logger.info(f"XGBoost — best iteration: {model.best_iteration}, best score: {model.best_score:.4f}")
    return model


def get_nn_probs(models: list[MatchPredictor], X: np.ndarray, temperature: float) -> np.ndarray:
    """Extrait les probabilités softmax moyennes de l'ensemble NN."""
    device = next(models[0].parameters()).device
    x_tensor = torch.tensor(X, dtype=torch.float32).to(device)

    avg_probs = torch.zeros(len(X), 3, device=device)
    with torch.no_grad():
        for model in models:
            model.eval()
            logits = model(x_tensor) / temperature
            avg_probs += torch.softmax(logits, dim=-1)
    avg_probs /= len(models)

    return avg_probs.cpu().numpy()


def build_meta_features(nn_probs: np.ndarray, xgb_probs: np.ndarray) -> np.ndarray:
    """Construit les features pour le méta-learner : 6 probas (3 NN + 3 XGB)."""
    return np.hstack([nn_probs, xgb_probs])


def run_training() -> bool:
    """Point d'entrée principal : NN Ensemble + XGBoost + Stacking."""
    logger.info("=" * 60)
    logger.info("ENTRAÎNEMENT STACKING : NN ENSEMBLE + XGBOOST")
    logger.info("=" * 60)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    session: Session = get_session()

    try:
        # 1. Chargement des données
        df: pd.DataFrame = load_training_data(session)
        if df.empty:
            logger.error("Aucune donnée trouvée.")
            return False

        # 2. Préparation des datasets
        train_dataset, val_dataset, test_dataset, scaler_params, class_weights, splits = prepare_datasets(df)
        X_train, y_train = splits["X_train"], splits["y_train"]
        X_val, y_val = splits["X_val"], splits["y_val"]
        X_test, y_test = splits["X_test"], splits["y_test"]

        # ============================================================
        # 3. ÉTAPE 1 — NN Ensemble
        # ============================================================
        ensemble_seeds = TRAIN_CONFIG["ensemble_seeds"]
        models: list[MatchPredictor] = []
        all_train_metrics: list[dict] = []

        for i, seed in enumerate(ensemble_seeds):
            logger.info(f"\n{'='*40} NN {i+1}/{len(ensemble_seeds)} (seed={seed}) {'='*40}")
            torch.manual_seed(seed)
            np.random.seed(seed)
            model, train_metrics = train_model(train_dataset, val_dataset, class_weights)
            models.append(model)
            all_train_metrics.append(train_metrics)

        best_model_idx = min(range(len(all_train_metrics)), key=lambda i: all_train_metrics[i]["best_val_loss"])
        temperature = calibrate_temperature(models[best_model_idx], val_dataset)

        # Évaluation NN seul
        nn_test_metrics = evaluate_ensemble(models, test_dataset, temperature)
        logger.info(f"NN Ensemble seul — Test Acc: {nn_test_metrics['test_accuracy']:.3f}")

        # ============================================================
        # 4. ÉTAPE 2 — XGBoost
        # ============================================================
        logger.info(f"\n{'='*40} XGBoost {'='*40}")
        xgb_model = train_xgboost(X_train, y_train, X_val, y_val)

        # Évaluation XGBoost seul
        xgb_test_preds = xgb_model.predict(X_test)
        xgb_test_acc = np.mean(xgb_test_preds == y_test)
        logger.info(f"XGBoost seul — Test Acc: {xgb_test_acc:.3f}")

        # ============================================================
        # 5. ÉTAPE 3 — Stacking avec méta-learner
        # ============================================================
        logger.info(f"\n{'='*40} STACKING {'='*40}")

        # Générer les probabilités NN et XGBoost sur validation (pour entraîner le méta-learner)
        nn_val_probs = get_nn_probs(models, X_val, temperature)
        xgb_val_probs = xgb_model.predict_proba(X_val)
        meta_X_val = build_meta_features(nn_val_probs, xgb_val_probs)

        # Méta-learner : LogisticRegression sur les 6 probas
        meta_model = LogisticRegression(
            max_iter=1000,
            solver="lbfgs",
            C=1.0,
        )
        meta_model.fit(meta_X_val, y_val)

        # Évaluation stacking sur test
        nn_test_probs = get_nn_probs(models, X_test, temperature)
        xgb_test_probs = xgb_model.predict_proba(X_test)
        meta_X_test = build_meta_features(nn_test_probs, xgb_test_probs)
        meta_test_preds = meta_model.predict(meta_X_test)
        meta_test_acc = np.mean(meta_test_preds == y_test)

        # Per-class stacking
        class_correct = {0: 0, 1: 0, 2: 0}
        class_total = {0: 0, 1: 0, 2: 0}
        for pred, true in zip(meta_test_preds, y_test):
            class_total[true] += 1
            if pred == true:
                class_correct[true] += 1
        per_class_acc = {
            "H": round(class_correct[0] / max(class_total[0], 1), 3),
            "D": round(class_correct[1] / max(class_total[1], 1), 3),
            "A": round(class_correct[2] / max(class_total[2], 1), 3),
        }
        logger.info(f"STACKING Test Accuracy : {meta_test_acc:.3f}")
        logger.info(f"Par classe — H: {per_class_acc['H']}, D: {per_class_acc['D']}, A: {per_class_acc['A']}")

        # ============================================================
        # 6. Détermination du meilleur modèle
        # ============================================================
        results = {
            "nn_ensemble": nn_test_metrics["test_accuracy"],
            "xgboost": round(float(xgb_test_acc), 4),
            "stacking": round(float(meta_test_acc), 4),
        }
        best_approach = max(results, key=results.get)
        logger.info(f"\nRésultats: NN={results['nn_ensemble']:.3f}, XGB={results['xgboost']:.3f}, Stack={results['stacking']:.3f}")
        logger.info(f"Meilleur : {best_approach} ({results[best_approach]:.3f})")

        # ============================================================
        # 7. Sauvegarde
        # ============================================================
        # Toujours sauvegarder tous les composants (le predict.py choisira)
        ensemble_state = {
            "num_models": len(models),
            "model_config": DEFAULT_MODEL_CONFIG,
            "scaler_params": scaler_params,
            "temperature": temperature,
            "best_approach": best_approach,
            "results": results,
        }
        for i, model in enumerate(models):
            ensemble_state[f"model_{i}_state_dict"] = model.state_dict()

        torch.save(ensemble_state, MODEL_PATH)

        xgb_model.save_model(str(XGBOOST_PATH))

        with open(META_MODEL_PATH, "wb") as f:
            pickle.dump(meta_model, f)

        with open(SCALER_PATH, "w") as f:
            json.dump(scaler_params, f, indent=2)

        test_metrics = {
            "test_accuracy": results[best_approach],
            "per_class_accuracy": per_class_acc if best_approach == "stacking" else nn_test_metrics.get("per_class_accuracy", {}),
            "test_samples": len(y_test),
        }
        best_metrics = all_train_metrics[best_model_idx]
        all_metrics = {
            **best_metrics,
            **test_metrics,
            "ensemble_size": len(models),
            "temperature": temperature,
            "best_approach": best_approach,
            "all_results": results,
        }
        with open(METRICS_PATH, "w") as f:
            json.dump(all_metrics, f, indent=2)

        logger.info("=" * 60)
        logger.info("ENTRAÎNEMENT STACKING TERMINÉ AVEC SUCCÈS")
        logger.info(f"  NN Ensemble     : {results['nn_ensemble']:.3f}")
        logger.info(f"  XGBoost         : {results['xgboost']:.3f}")
        logger.info(f"  Stacking        : {results['stacking']:.3f}")
        logger.info(f"  Best            : {best_approach} ({results[best_approach]:.3f})")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale durant l'entraînement : {e}", exc_info=True)
        return False

    finally:
        session.close()


def evaluate_ensemble(
    models: list[MatchPredictor], test_dataset: TensorDataset, temperature: float
) -> dict:
    """Évalue l'ensemble de modèles sur le jeu de test avec temperature scaling."""
    device: torch.device = next(models[0].parameters()).device
    test_loader = DataLoader(test_dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=False)

    correct: int = 0
    total: int = 0
    class_correct: dict[int, int] = {0: 0, 1: 0, 2: 0}
    class_total: dict[int, int] = {0: 0, 1: 0, 2: 0}

    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)

            # Moyenne des probabilités softmax de tous les modèles
            avg_probs = torch.zeros(X_batch.size(0), 3, device=device)
            for model in models:
                model.eval()
                logits = model(X_batch) / temperature
                avg_probs += torch.softmax(logits, dim=-1)
            avg_probs /= len(models)

            preds: torch.Tensor = avg_probs.argmax(dim=-1)
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)

            for cls in range(3):
                mask = y_batch == cls
                class_correct[cls] += (preds[mask] == cls).sum().item()
                class_total[cls] += mask.sum().item()

    test_acc: float = correct / max(total, 1)
    per_class_acc: dict[str, float] = {
        "H": round(class_correct[0] / max(class_total[0], 1), 3),
        "D": round(class_correct[1] / max(class_total[1], 1), 3),
        "A": round(class_correct[2] / max(class_total[2], 1), 3),
    }

    logger.info(f"Ensemble Test Accuracy : {test_acc:.3f}")
    logger.info(f"Par classe — H: {per_class_acc['H']}, D: {per_class_acc['D']}, A: {per_class_acc['A']}")

    return {"test_accuracy": round(test_acc, 4), "per_class_accuracy": per_class_acc, "test_samples": total}


if __name__ == "__main__":
    run_training()
