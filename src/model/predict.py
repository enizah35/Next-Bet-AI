"""
src/model/predict.py
Module d'inférence pour charger le modèle entraîné et prédire des résultats.
Supporte l'ensemble NN + XGBoost + stacking.
"""

import json
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import xgboost as xgb

from src.model.network import MatchPredictor, CLASS_LABELS

logger: logging.Logger = logging.getLogger(__name__)

# Chemins des checkpoints
MODEL_DIR: Path = Path(__file__).parent / "checkpoints"
MODEL_PATH: Path = MODEL_DIR / "match_predictor.pt"
XGBOOST_PATH: Path = MODEL_DIR / "xgboost_model.json"
META_MODEL_PATH: Path = MODEL_DIR / "meta_model.pkl"


class MatchPredictorService:
    """Service singleton pour charger et utiliser l'ensemble NN + XGBoost + stacking."""

    def __init__(self) -> None:
        self.models: list[MatchPredictor] = []
        self.temperature: float = 1.0
        self.scaler_mean: Optional[np.ndarray] = None
        self.scaler_scale: Optional[np.ndarray] = None
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_loaded: bool = False
        self.best_approach: str = "nn_ensemble"
        self.xgb_model: Optional[xgb.XGBClassifier] = None
        self.meta_model = None

    def load(self) -> bool:
        """Charge le checkpoint NN + XGBoost + meta-learner."""
        if not MODEL_PATH.exists():
            logger.warning(f"Checkpoint introuvable : {MODEL_PATH}")
            return False

        try:
            checkpoint: dict = torch.load(MODEL_PATH, map_location=self.device, weights_only=False)
            config: dict = checkpoint["model_config"]
            self.best_approach = checkpoint.get("best_approach", "nn_ensemble")

            if "num_models" in checkpoint:
                n = checkpoint["num_models"]
                self.temperature = checkpoint.get("temperature", 1.0)
                self.models = []
                for i in range(n):
                    model = MatchPredictor(**config).to(self.device)
                    model.load_state_dict(checkpoint[f"model_{i}_state_dict"])
                    model.eval()
                    self.models.append(model)
                logger.info(f"Ensemble NN chargé : {n} modèles, T={self.temperature:.2f}")
            else:
                model = MatchPredictor(**config).to(self.device)
                model.load_state_dict(checkpoint["model_state_dict"])
                model.eval()
                self.models = [model]
                self.temperature = 1.0

            # Scaler
            scaler_params: dict = checkpoint["scaler_params"]
            self.scaler_mean = np.array(scaler_params["mean"], dtype=np.float32)
            self.scaler_scale = np.array(scaler_params["scale"], dtype=np.float32)
            self.feature_columns = scaler_params.get("feature_columns", [])

            # XGBoost
            if XGBOOST_PATH.exists():
                self.xgb_model = xgb.XGBClassifier()
                self.xgb_model.load_model(str(XGBOOST_PATH))
                logger.info("XGBoost chargé")

            # Meta-learner
            if META_MODEL_PATH.exists():
                with open(META_MODEL_PATH, "rb") as f:
                    self.meta_model = pickle.load(f)
                logger.info("Meta-learner chargé")

            logger.info(f"Best approach : {self.best_approach}")
            self.is_loaded = True
            return True

        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle : {e}", exc_info=True)
            return False

    def _get_nn_probs(self, features_scaled: np.ndarray) -> np.ndarray:
        """Probabilités softmax moyennes de l'ensemble NN."""
        x = torch.tensor(features_scaled, dtype=torch.float32).to(self.device)
        avg_probs = torch.zeros(features_scaled.shape[0], 3, device=self.device)
        with torch.no_grad():
            for model in self.models:
                logits = model(x) / self.temperature
                avg_probs += torch.softmax(logits, dim=-1)
        avg_probs /= len(self.models)
        return avg_probs.cpu().numpy()

    def predict(
        self,
        implied_away: float = 0.32,
        implied_home: float = 0.40,
        implied_draw: float = 0.28,
        away_elo: float = 1500.0,
        elo_diff: float = 0.0,
        home_elo: float = 1500.0,
        home_goals_conceded_last_5: float = 1.0,
        away_goals_scored_last_5: float = 1.0,
        away_pts_last_5: float = 1.5,
        home_pts_last_5_at_home: float = 1.5,
        away_pts_last_5_away: float = 1.5,
        away_sot_last_5: float = 4.0,
        home_sot_last_5: float = 4.0,
        away_sot_conceded_last_5: float = 4.0,
        **kwargs,
    ) -> dict:
        """
        Prédit le résultat d'un match avec 14 features + stacking.
        Utilise le best_approach sauvegardé à l'entraînement.
        """
        if not self.is_loaded:
            raise RuntimeError("Le modèle n'est pas chargé. Appelez load() d'abord.")

        features: np.ndarray = np.array(
            [[
                implied_away, implied_home, implied_draw,
                away_elo, elo_diff, home_elo,
                home_goals_conceded_last_5, away_goals_scored_last_5, away_pts_last_5,
                home_pts_last_5_at_home, away_pts_last_5_away,
                away_sot_last_5, home_sot_last_5, away_sot_conceded_last_5,
            ]],
            dtype=np.float32,
        )

        # Normalisation
        features = (features - self.scaler_mean) / self.scaler_scale

        # NN probs (toujours nécessaires)
        nn_probs = self._get_nn_probs(features)

        # Choix de la méthode d'inférence
        if self.best_approach == "stacking" and self.xgb_model is not None and self.meta_model is not None:
            xgb_probs = self.xgb_model.predict_proba(features)
            meta_features = np.hstack([nn_probs, xgb_probs])
            probs = self.meta_model.predict_proba(meta_features)[0]
        elif self.best_approach == "xgboost" and self.xgb_model is not None:
            probs = self.xgb_model.predict_proba(features)[0]
        else:
            probs = nn_probs[0]

        # Résultat
        pred_idx: int = int(probs.argmax())
        prediction: str = CLASS_LABELS[pred_idx]
        confidence: float = float(probs[pred_idx])

        return {
            "prediction": prediction,
            "probabilities": {
                "home_win": round(float(probs[0]), 4),
                "draw": round(float(probs[1]), 4),
                "away_win": round(float(probs[2]), 4),
            },
            "confidence": round(confidence, 4),
        }


# Instance singleton
predictor_service: MatchPredictorService = MatchPredictorService()
