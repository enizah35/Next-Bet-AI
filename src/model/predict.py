"""
src/model/predict.py
Module d'inférence pour charger le modèle entraîné et prédire des résultats.
Supporte les 17 features avancées (Elo, forme dom/ext, fatigue, xG/xPTS).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from src.model.network import MatchPredictor, CLASS_LABELS

logger: logging.Logger = logging.getLogger(__name__)

# Chemin du checkpoint
MODEL_DIR: Path = Path(__file__).parent / "checkpoints"
MODEL_PATH: Path = MODEL_DIR / "match_predictor.pt"


class MatchPredictorService:
    """Service singleton pour charger et utiliser le modèle entraîné."""

    def __init__(self) -> None:
        self.model: Optional[MatchPredictor] = None
        self.scaler_mean: Optional[np.ndarray] = None
        self.scaler_scale: Optional[np.ndarray] = None
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_loaded: bool = False

    def load(self) -> bool:
        """Charge le modèle et le scaler depuis le checkpoint."""
        if not MODEL_PATH.exists():
            logger.warning(f"Checkpoint introuvable : {MODEL_PATH}")
            return False

        try:
            checkpoint: dict = torch.load(MODEL_PATH, map_location=self.device, weights_only=False)

            # Reconstruction du modèle
            config: dict = checkpoint["model_config"]
            self.model = MatchPredictor(**config).to(self.device)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.eval()

            # Chargement des paramètres du scaler
            scaler_params: dict = checkpoint["scaler_params"]
            self.scaler_mean = np.array(scaler_params["mean"], dtype=np.float32)
            self.scaler_scale = np.array(scaler_params["scale"], dtype=np.float32)

            self.is_loaded = True
            logger.info(f"Modèle chargé ({config['input_dim']} features) depuis {MODEL_PATH}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle : {e}", exc_info=True)
            return False

    def predict(
        self,
        home_pts_last_5: float,
        home_goals_scored_last_5: float,
        home_goals_conceded_last_5: float,
        away_pts_last_5: float,
        away_goals_scored_last_5: float,
        away_goals_conceded_last_5: float,
        home_elo: float = 1500.0,
        away_elo: float = 1500.0,
        elo_diff: float = 0.0,
        home_pts_last_5_at_home: float = 1.5,
        away_pts_last_5_away: float = 1.5,
        home_days_rest: float = 7.0,
        away_days_rest: float = 7.0,
        home_xg_last_5: float = 1.1,
        home_xpts_last_5: float = 1.1,
        away_xg_last_5: float = 1.1,
        away_xpts_last_5: float = 1.1,
    ) -> dict:
        """
        Prédit le résultat d'un match avec les 15 features.

        Returns:
            dict avec 'prediction' (H/D/A), 'probabilities', 'confidence'
        """
        if not self.is_loaded:
            raise RuntimeError("Le modèle n'est pas chargé. Appelez load() d'abord.")

        # Vecteur de 15 features (même ordre que FEATURE_COLUMNS dans train.py)
        features: np.ndarray = np.array(
            [[
                home_pts_last_5, home_goals_scored_last_5, home_goals_conceded_last_5,
                away_pts_last_5, away_goals_scored_last_5, away_goals_conceded_last_5,
                home_elo, away_elo, elo_diff,
                home_pts_last_5_at_home, away_pts_last_5_away,
                home_days_rest, away_days_rest,
                home_xg_last_5, home_xpts_last_5,
                away_xg_last_5, away_xpts_last_5,
            ]],
            dtype=np.float32,
        )

        # Normalisation avec les paramètres du scaler d'entraînement
        features = (features - self.scaler_mean) / self.scaler_scale

        # Inférence
        x: torch.Tensor = torch.tensor(features, dtype=torch.float32).to(self.device)
        probabilities: torch.Tensor = self.model.predict_proba(x)
        probs: np.ndarray = probabilities.cpu().numpy()[0]

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
