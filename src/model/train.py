"""
src/model/train.py
Script d'entraînement du modèle MatchPredictor.
Charge les données depuis PostgreSQL, entraîne le réseau, et sauvegarde le checkpoint.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
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
    "epochs": 200,
    "batch_size": 64,
    "learning_rate": 0.0005,
    "weight_decay": 1e-4,
    "patience": 40,         # Early stopping patience
    "val_split": 0.1,
    "test_split": 0.05,
    "random_state": 13,
}

# Colonnes features utilisées pour l'entraînement (15 features)
FEATURE_COLUMNS: list[str] = [
    # Forme générale (6)
    "home_pts_last_5",
    "home_goals_scored_last_5",
    "home_goals_conceded_last_5",
    "away_pts_last_5",
    "away_goals_scored_last_5",
    "away_goals_conceded_last_5",
    # Elo (3)
    "home_elo",
    "away_elo",
    "elo_diff",
    # Forme spécifique dom/ext (2)
    "home_pts_last_5_at_home",
    "away_pts_last_5_away",
    # Fatigue (2)
    "home_days_rest",
    "away_days_rest",
    # Understat (xG & xPts) (4)
    "home_xg_last_5",
    "home_xpts_last_5",
    "away_xg_last_5",
    "away_xpts_last_5",
]


def load_training_data(session: Session) -> pd.DataFrame:
    """Charge les 15 features et les résultats depuis PostgreSQL."""
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
            # Forme spécifique
            MatchFeature.home_pts_last_5_at_home,
            MatchFeature.away_pts_last_5_away,
            # Fatigue
            MatchFeature.home_days_rest,
            MatchFeature.away_days_rest,
            # Understat
            MatchFeature.home_xg_last_5,
            MatchFeature.home_xpts_last_5,
            MatchFeature.away_xg_last_5,
            MatchFeature.away_xpts_last_5,
            # Target
            MatchRaw.ftr,
        )
        .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
        .order_by(MatchRaw.date)
    )

    result = session.execute(stmt)
    rows = result.fetchall()

    df: pd.DataFrame = pd.DataFrame(
        rows,
        columns=["match_id"] + FEATURE_COLUMNS + ["ftr"],
    )

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

    return train_dataset, val_dataset, test_dataset, scaler_params, class_weights


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

    # Loss sans poids de classe pour maximiser l'accuracy brute (objectif > 0.55)
    criterion = nn.CrossEntropyLoss()

    # Optimiseur + Scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.0005,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=8
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


def run_training() -> bool:
    """Point d'entrée principal de l'entraînement."""
    logger.info("=" * 60)
    logger.info("DÉMARRAGE DE L'ENTRAÎNEMENT DU MODÈLE DEEP LEARNING")
    logger.info("=" * 60)

    # Création du dossier checkpoints
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    session: Session = get_session()

    try:
        # 1. Chargement des données
        df: pd.DataFrame = load_training_data(session)
        if df.empty:
            logger.error("Aucune donnée trouvée. Exécutez l'ingestion et le feature engineering d'abord.")
            return False

        # 2. Préparation des datasets
        train_dataset, val_dataset, test_dataset, scaler_params, class_weights = prepare_datasets(df)

        # 3. Entraînement
        model, train_metrics = train_model(train_dataset, val_dataset, class_weights)

        # 4. Évaluation sur le jeu de test
        test_metrics: dict = evaluate_model(model, test_dataset)

        # 5. Sauvegarde du modèle
        torch.save({
            "model_state_dict": model.state_dict(),
            "model_config": DEFAULT_MODEL_CONFIG,
            "scaler_params": scaler_params,
        }, MODEL_PATH)
        logger.info(f"Modèle sauvegardé : {MODEL_PATH}")

        # 6. Sauvegarde des paramètres du scaler
        with open(SCALER_PATH, "w") as f:
            json.dump(scaler_params, f, indent=2)
        logger.info(f"Scaler sauvegardé : {SCALER_PATH}")

        # 7. Sauvegarde des métriques
        all_metrics: dict = {**train_metrics, **test_metrics}
        with open(METRICS_PATH, "w") as f:
            json.dump(all_metrics, f, indent=2)
        logger.info(f"Métriques sauvegardées : {METRICS_PATH}")

        logger.info("=" * 60)
        logger.info("ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS")
        logger.info(f"  Val Accuracy  : {train_metrics['best_val_acc']:.3f}")
        logger.info(f"  Test Accuracy : {test_metrics['test_accuracy']:.3f}")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale durant l'entraînement : {e}", exc_info=True)
        return False

    finally:
        session.close()


if __name__ == "__main__":
    run_training()
