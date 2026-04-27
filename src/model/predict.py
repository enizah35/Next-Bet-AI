"""
src/model/predict.py
Inference avec modele global + modeles specialises par ligue.
"""

import logging
import json
import os
import pickle
from dataclasses import dataclass
from pathlib import Path

import lightgbm as lgb
import numpy as np
import torch
import xgboost as xgb

from src.model.network import MatchPredictor, CLASS_LABELS
from src.model.train import FEATURE_COLUMNS

logger: logging.Logger = logging.getLogger(__name__)

MODEL_DIR: Path = Path(__file__).parent / "checkpoints"
MODEL_PATH: Path = MODEL_DIR / "match_predictor.pt"
XGBOOST_PATH: Path = MODEL_DIR / "xgboost_model.json"
LIGHTGBM_PATH: Path = MODEL_DIR / "lightgbm_model.txt"
META_MODEL_PATH: Path = MODEL_DIR / "meta_model.pkl"
DRAW_MODEL_PATH: Path = MODEL_DIR / "draw_model.txt"
LEAGUE_MODELS_DIR: Path = MODEL_DIR / "leagues"

LEAGUE_NAME_TO_DIV: dict[str, str] = {
    "Ligue 1": "F1",
    "Premier League": "E0",
    "Bundesliga": "D1",
    "La Liga": "SP1",
    "Serie A": "I1",
    "Championship": "E1",
    "Ligue 2": "F2",
    "2. Bundesliga": "D2",
    "La Liga 2": "SP2",
    "Serie B": "I2",
    "Eredivisie": "N1",
    "Primeira Liga": "P1",
    "Süper Lig": "T1",
    "SÃ¼per Lig": "T1",
    "Super Lig": "T1",
    "Belgian Pro League": "B1",
    "Scottish Premiership": "SC0",
}


@dataclass
class ModelBundle:
    """Tous les artefacts necessaires pour predire avec un checkpoint."""

    name: str
    model_dir: Path
    models: list[MatchPredictor]
    temperature: float
    scaler_mean: np.ndarray
    scaler_scale: np.ndarray
    feature_columns: list[str]
    best_approach: str
    xgb_model: xgb.XGBClassifier | None
    lgb_model: lgb.Booster | None
    meta_model: object | None
    draw_model: lgb.Booster | None
    market_baseline_test_accuracy: float | None
    test_accuracy: float | None
    best_vs_market_delta: float | None


def normalize_league_key(league: str | None) -> str | None:
    if not league:
        return None

    raw = league.strip()
    upper = raw.upper()
    valid_codes = set(LEAGUE_NAME_TO_DIV.values())
    if upper in valid_codes:
        return upper

    lowered = {name.lower(): code for name, code in LEAGUE_NAME_TO_DIV.items()}
    return lowered.get(raw.lower())


class MatchPredictorService:
    """Charge un modele global et, si disponibles, des modeles specialises par ligue."""

    def __init__(self) -> None:
        self.device: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.global_bundle: ModelBundle | None = None
        self.league_bundles: dict[str, ModelBundle] = {}
        self.is_loaded: bool = False
        self.min_league_delta: float = float(os.getenv("LEAGUE_MODEL_MIN_DELTA", "-999"))

        # Champs historiques gardes pour compatibilite avec le reste du projet.
        self.models: list[MatchPredictor] = []
        self.temperature: float = 1.0
        self.scaler_mean: np.ndarray | None = None
        self.scaler_scale: np.ndarray | None = None
        self.feature_columns: list[str] = []
        self.best_approach: str = "nn_ensemble"
        self.xgb_model: xgb.XGBClassifier | None = None
        self.lgb_model: lgb.Booster | None = None
        self.meta_model = None
        self.draw_model: lgb.Booster | None = None

    def _artifact_path(self, model_dir: Path, base_path: Path) -> Path:
        return model_dir / base_path.name

    def _load_bundle(self, model_dir: Path, name: str) -> ModelBundle | None:
        model_path = self._artifact_path(model_dir, MODEL_PATH)
        if not model_path.exists():
            return None

        try:
            checkpoint: dict = torch.load(model_path, map_location=self.device, weights_only=False)
            config: dict = checkpoint["model_config"]
            best_approach = checkpoint.get("best_approach", "nn_ensemble")

            n = checkpoint.get("num_models", 1)
            temperature = checkpoint.get("temperature", 1.0)
            models: list[MatchPredictor] = []
            for i in range(n):
                model = MatchPredictor(**config).to(self.device)
                key = f"model_{i}_state_dict"
                if key not in checkpoint and n == 1:
                    key = "model_state_dict"
                model.load_state_dict(checkpoint[key])
                model.eval()
                models.append(model)

            scaler_params: dict = checkpoint["scaler_params"]
            scaler_mean = np.array(scaler_params["mean"], dtype=np.float32)
            scaler_scale = np.array(scaler_params["scale"], dtype=np.float32)
            feature_columns = scaler_params.get("feature_columns", FEATURE_COLUMNS)

            xgb_model = None
            xgb_path = self._artifact_path(model_dir, XGBOOST_PATH)
            if xgb_path.exists():
                xgb_model = xgb.XGBClassifier()
                xgb_model.load_model(str(xgb_path))

            lgb_model = None
            lgb_path = self._artifact_path(model_dir, LIGHTGBM_PATH)
            if lgb_path.exists():
                lgb_model = lgb.Booster(model_file=str(lgb_path))

            meta_model = None
            meta_path = self._artifact_path(model_dir, META_MODEL_PATH)
            if meta_path.exists():
                with open(meta_path, "rb") as f:
                    meta_model = pickle.load(f)

            draw_model = None
            draw_path = self._artifact_path(model_dir, DRAW_MODEL_PATH)
            if draw_path.exists():
                draw_model = lgb.Booster(model_file=str(draw_path))

            metrics = {}
            metrics_path = model_dir / "training_metrics.json"
            if metrics_path.exists():
                with open(metrics_path, "r") as f:
                    metrics = json.load(f)

            bundle = ModelBundle(
                name=name,
                model_dir=model_dir,
                models=models,
                temperature=temperature,
                scaler_mean=scaler_mean,
                scaler_scale=scaler_scale,
                feature_columns=feature_columns,
                best_approach=best_approach,
                xgb_model=xgb_model,
                lgb_model=lgb_model,
                meta_model=meta_model,
                draw_model=draw_model,
                market_baseline_test_accuracy=checkpoint.get("market_baseline_test_accuracy"),
                test_accuracy=metrics.get("test_accuracy"),
                best_vs_market_delta=metrics.get("best_vs_market_delta"),
            )
            logger.info("Modele charge : %s (%s, best=%s)", name, model_dir, best_approach)
            return bundle

        except Exception as e:
            logger.error("Erreur chargement modele %s : %s", model_dir, e, exc_info=True)
            return None

    def _sync_legacy_fields(self, bundle: ModelBundle) -> None:
        self.models = bundle.models
        self.temperature = bundle.temperature
        self.scaler_mean = bundle.scaler_mean
        self.scaler_scale = bundle.scaler_scale
        self.feature_columns = bundle.feature_columns
        self.best_approach = bundle.best_approach
        self.xgb_model = bundle.xgb_model
        self.lgb_model = bundle.lgb_model
        self.meta_model = bundle.meta_model
        self.draw_model = bundle.draw_model

    def load(self) -> bool:
        """Charge le modele global puis tous les checkpoints presents dans checkpoints/leagues."""
        self.global_bundle = self._load_bundle(MODEL_DIR, "global")
        self.league_bundles = {}

        if LEAGUE_MODELS_DIR.exists():
            for child in sorted(LEAGUE_MODELS_DIR.iterdir()):
                if not child.is_dir():
                    continue
                code = child.name.upper()
                bundle = self._load_bundle(child, code)
                if bundle:
                    self.league_bundles[code] = bundle

        if self.global_bundle:
            self._sync_legacy_fields(self.global_bundle)
        elif self.league_bundles:
            self._sync_legacy_fields(next(iter(self.league_bundles.values())))

        self.is_loaded = self.global_bundle is not None or bool(self.league_bundles)
        if self.is_loaded:
            logger.info("Modeles ligue charges : %s", sorted(self.league_bundles.keys()))
        else:
            logger.warning("Aucun checkpoint modele trouve.")
        return self.is_loaded

    def _select_bundle(self, league: str | None) -> tuple[ModelBundle, str]:
        league_code = normalize_league_key(league)
        if league_code and league_code in self.league_bundles:
            bundle = self.league_bundles[league_code]
            delta = bundle.best_vs_market_delta
            if delta is None or delta >= self.min_league_delta:
                return bundle, league_code
            logger.info(
                "Modele %s ignore: delta marche %.4f < seuil %.4f",
                league_code,
                delta,
                self.min_league_delta,
            )

        if self.global_bundle:
            return self.global_bundle, "global"

        if self.league_bundles:
            first_code, first_bundle = next(iter(self.league_bundles.items()))
            return first_bundle, first_code

        raise RuntimeError("Modele non charge. Appelez load() d'abord.")

    def _build_feature_vector(self, bundle: ModelBundle, **kwargs) -> tuple[np.ndarray, np.ndarray]:
        vec = bundle.scaler_mean.copy()
        for i, col in enumerate(bundle.feature_columns):
            if col not in kwargs or kwargs[col] is None:
                continue
            try:
                value = float(kwargs[col])
            except (TypeError, ValueError):
                continue
            if np.isfinite(value):
                vec[i] = value

        features_raw = vec.reshape(1, -1)
        features_scaled = (features_raw - bundle.scaler_mean) / bundle.scaler_scale
        return features_raw, features_scaled

    def _get_nn_probs(self, bundle: ModelBundle, features_scaled: np.ndarray) -> np.ndarray:
        x = torch.tensor(features_scaled, dtype=torch.float32).to(self.device)
        avg_probs = torch.zeros(features_scaled.shape[0], 3, device=self.device)
        with torch.no_grad():
            for model in bundle.models:
                avg_probs += torch.softmax(model(x) / bundle.temperature, dim=-1)
        avg_probs /= len(bundle.models)
        return avg_probs.cpu().numpy()

    def predict(self, league: str | None = None, **kwargs) -> dict:
        """
        Predit le resultat d'un match.
        Si `league` correspond a un checkpoint specialise, il est utilise en priorite.
        """
        bundle, scope = self._select_bundle(league)
        features_raw, features = self._build_feature_vector(bundle, **kwargs)

        nn_probs = self._get_nn_probs(bundle, features)

        if bundle.best_approach == "stacking" and bundle.meta_model is not None:
            xgb_probs = (
                bundle.xgb_model.predict_proba(features)
                if bundle.xgb_model is not None
                else np.ones((1, 3)) / 3
            )
            lgb_probs = (
                bundle.lgb_model.predict(features)
                if bundle.lgb_model is not None
                else np.ones((1, 3)) / 3
            )
            if lgb_probs.ndim == 1:
                lgb_probs = lgb_probs.reshape(1, -1)
            implied_odds = features_raw[:, :3]
            meta_features = np.hstack([nn_probs, xgb_probs, lgb_probs, implied_odds])
            probs = bundle.meta_model.predict_proba(meta_features)[0]

        elif bundle.best_approach == "lightgbm" and bundle.lgb_model is not None:
            probs = bundle.lgb_model.predict(features)[0]

        elif bundle.best_approach == "xgboost" and bundle.xgb_model is not None:
            probs = bundle.xgb_model.predict_proba(features)[0]

        else:
            probs = nn_probs[0]

        draw_specialist_prob = None
        if bundle.draw_model is not None:
            try:
                draw_specialist_prob = float(bundle.draw_model.predict(features)[0])
                blend = float(os.getenv("DRAW_SPECIALIST_BLEND", "0.25"))
                blend = max(0.0, min(0.6, blend))
                probs = probs.astype(float).copy()
                probs[1] = (probs[1] * (1.0 - blend)) + (draw_specialist_prob * blend)
                non_draw_total = probs[0] + probs[2]
                remaining = max(1e-6, 1.0 - probs[1])
                if non_draw_total > 0:
                    probs[0] = remaining * probs[0] / non_draw_total
                    probs[2] = remaining * probs[2] / non_draw_total
            except Exception as e:
                logger.debug(f"Draw specialist ignoré: {e}")

        pred_idx = int(probs.argmax())
        return {
            "prediction": CLASS_LABELS[pred_idx],
            "probabilities": {
                "home_win": round(float(probs[0]), 4),
                "draw": round(float(probs[1]), 4),
                "away_win": round(float(probs[2]), 4),
            },
            "confidence": round(float(probs[pred_idx]), 4),
            "model_scope": scope,
            "model_best_approach": bundle.best_approach,
            "model_test_accuracy": bundle.test_accuracy,
            "model_vs_market_delta": bundle.best_vs_market_delta,
            "draw_specialist_prob": round(draw_specialist_prob, 4) if draw_specialist_prob is not None else None,
        }


predictor_service: MatchPredictorService = MatchPredictorService()
