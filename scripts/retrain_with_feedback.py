"""
scripts/retrain_with_feedback.py
Feedback loop : re-entraîne le méta-learner en intégrant les prédictions vérifiées.

Cache : les données intermédiaires coûteuses (splits, meta-features) sont mises en cache
dans MODEL_DIR/retrain_cache/ et réutilisées si les sources n'ont pas changé.
  - Cache splits/meta-features invalidé si le checkpoint est modifié (mtime).
  - Cache feedback invalidé si le nombre de prédictions vérifiées change.

Logique :
  1. Charge le checkpoint complet (NN + XGB + LGB + méta-learner).
  2. Lit les prédictions vérifiées depuis prediction_logs.
  3. Divise les feedbacks chronologiquement : 80% train / 20% held-out.
  4. Ré-entraîne le GradientBoosting méta-learner sur :
       val original (1x) + feedback_train (FEEDBACK_WEIGHT x)
  5. Évalue sur X_test original + feedback_test (held-out — jamais vus).
  6. Sauvegarde uniquement si la précision ne régresse pas.

Usage :
  python -m scripts.retrain_with_feedback [--min-samples 30] [--clear-cache]
"""

import argparse
import json
import logging
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np
import torch
from sklearn.ensemble import GradientBoostingClassifier
from sqlalchemy import select, func

from src.database.database import get_session
from src.database.models import PredictionLog
from src.model.network import MatchPredictor, LABEL_TO_INDEX
from src.model.train import FEATURE_COLUMNS, load_training_data, prepare_datasets, get_nn_probs
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent.parent / "src" / "model" / "checkpoints"
MODEL_PATH = MODEL_DIR / "match_predictor.pt"
XGBOOST_PATH = MODEL_DIR / "xgboost_model.json"
LIGHTGBM_PATH = MODEL_DIR / "lightgbm_model.txt"
META_MODEL_PATH = MODEL_DIR / "meta_model.pkl"
CACHE_DIR = MODEL_DIR / "retrain_cache"

FEEDBACK_WEIGHT = 3
MIN_FEEDBACK_SAMPLES = 30
FEEDBACK_TRAIN_RATIO = 0.80
MIN_ACCURACY_DELTA = -0.005


# ============================================================
# Cache helpers
# ============================================================

def _checkpoint_mtime() -> float:
    """Horodatage du checkpoint NN — sert de clé de cache pour splits/meta-features."""
    return MODEL_PATH.stat().st_mtime if MODEL_PATH.exists() else 0.0


def _read_cache_meta() -> dict:
    meta_file = CACHE_DIR / "cache_meta.json"
    if meta_file.exists():
        try:
            return json.loads(meta_file.read_text())
        except Exception:
            pass
    return {}


def _write_cache_meta(meta: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / "cache_meta.json").write_text(json.dumps(meta, indent=2))


def _load_npz(name: str) -> dict | None:
    path = CACHE_DIR / f"{name}.npz"
    if path.exists():
        try:
            return dict(np.load(path, allow_pickle=False))
        except Exception:
            pass
    return None


def _save_npz(name: str, **arrays) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(CACHE_DIR / f"{name}.npz", **arrays)


def clear_cache() -> None:
    if CACHE_DIR.exists():
        for f in CACHE_DIR.iterdir():
            f.unlink()
        CACHE_DIR.rmdir()
    logger.info("Cache supprimé.")


# ============================================================
# Model loading
# ============================================================

def load_models(device: torch.device):
    checkpoint = torch.load(MODEL_PATH, map_location=device, weights_only=False)
    config = checkpoint["model_config"]
    temperature = checkpoint.get("temperature", 1.0)
    scaler_params = checkpoint["scaler_params"]

    models = []
    for i in range(checkpoint.get("num_models", 1)):
        m = MatchPredictor(**config).to(device)
        m.load_state_dict(checkpoint[f"model_{i}_state_dict"])
        m.eval()
        models.append(m)

    xgb_model = xgb.XGBClassifier()
    xgb_model.load_model(str(XGBOOST_PATH))

    lgb_model = lgb.Booster(model_file=str(LIGHTGBM_PATH))

    with open(META_MODEL_PATH, "rb") as f:
        meta_model = pickle.load(f)

    return models, temperature, scaler_params, xgb_model, lgb_model, meta_model


def build_meta_features(nn_probs, xgb_probs, lgb_probs, X_scaled):
    implied = X_scaled[:, :3]
    if lgb_probs.ndim == 1:
        lgb_probs = lgb_probs.reshape(len(X_scaled), -1)
    return np.hstack([nn_probs, xgb_probs, lgb_probs, implied])


# ============================================================
# Cached: splits + meta-features for val/test
# ============================================================

def get_splits_and_meta(session, models, temperature, xgb_model, lgb_model) -> dict:
    """
    Retourne X_val, y_val, X_test, y_test, meta_val, meta_test.
    Utilise le cache si le checkpoint n'a pas changé depuis le dernier appel.
    """
    cache_meta = _read_cache_meta()
    current_mtime = _checkpoint_mtime()

    if cache_meta.get("checkpoint_mtime") == current_mtime:
        splits_cache = _load_npz("splits")
        meta_cache = _load_npz("meta_val_test")
        if splits_cache is not None and meta_cache is not None:
            logger.info("[cache] Splits + meta-features val/test chargés depuis le cache.")
            return {
                "X_val": splits_cache["X_val"],
                "y_val": splits_cache["y_val"],
                "X_test": splits_cache["X_test"],
                "y_test": splits_cache["y_test"],
                "meta_val": meta_cache["meta_val"],
                "meta_test": meta_cache["meta_test"],
            }

    logger.info("[DB] Chargement des données d'entraînement depuis la base...")
    df = load_training_data(session)
    _, _, _, _, _, splits = prepare_datasets(df)
    X_val, y_val = splits["X_val"], splits["y_val"]
    X_test, y_test = splits["X_test"], splits["y_test"]

    logger.info("[inférence] Calcul des meta-features val/test (NN + XGB + LGB)...")
    def _meta(X):
        nn = get_nn_probs(models, X, temperature)
        xg = xgb_model.predict_proba(X)
        lg = lgb_model.predict(X)
        return build_meta_features(nn, xg, lg, X)

    meta_val = _meta(X_val)
    meta_test = _meta(X_test)

    _save_npz("splits", X_val=X_val, y_val=y_val, X_test=X_test, y_test=y_test)
    _save_npz("meta_val_test", meta_val=meta_val, meta_test=meta_test)

    cache_meta["checkpoint_mtime"] = current_mtime
    _write_cache_meta(cache_meta)

    logger.info(f"[cache] Splits + meta-features sauvegardés (val={len(y_val)}, test={len(y_test)}).")
    return {"X_val": X_val, "y_val": y_val, "X_test": X_test, "y_test": y_test,
            "meta_val": meta_val, "meta_test": meta_test}


# ============================================================
# Cached: feedback samples from prediction_logs
# ============================================================

def get_feedback_samples(session, min_samples: int, scaler_mean, scaler_scale) -> dict | None:
    """
    Retourne X_fb_train, y_fb_train, meta_fb_train, meta_fb_test, y_fb_test.
    Cache invalidé si le nombre de prédictions vérifiées change.
    """
    # Compter les prédictions vérifiées disponibles
    verified_count = session.execute(
        select(func.count(PredictionLog.id)).where(
            PredictionLog.is_won.isnot(None),
            PredictionLog.features_json.isnot(None),
            PredictionLog.actual_result.isnot(None),
        )
    ).scalar() or 0

    logger.info(f"Prédictions vérifiées disponibles : {verified_count}")

    if verified_count < min_samples:
        logger.warning(f"Insuffisant ({verified_count} < {min_samples}). Annulé.")
        return None

    cache_meta = _read_cache_meta()

    if cache_meta.get("feedback_count") == verified_count:
        fb_cache = _load_npz("feedback")
        if fb_cache is not None:
            logger.info(f"[cache] Feedback ({verified_count} samples) chargé depuis le cache.")
            return {
                "X_fb_train": fb_cache["X_fb_train"],
                "y_fb_train": fb_cache["y_fb_train"],
                "meta_fb_train": fb_cache["meta_fb_train"],
                "meta_fb_test": fb_cache["meta_fb_test"] if "meta_fb_test" in fb_cache else None,
                "y_fb_test": fb_cache["y_fb_test"] if "y_fb_test" in fb_cache else None,
            }

    # Charger depuis la DB (ordre chronologique pour split honnête)
    stmt = (
        select(PredictionLog)
        .where(
            PredictionLog.is_won.isnot(None),
            PredictionLog.features_json.isnot(None),
            PredictionLog.actual_result.isnot(None),
        )
        .order_by(PredictionLog.match_date.asc())
        .limit(2000)
    )
    rows = session.execute(stmt).scalars().all()

    X_list, y_list = [], []
    for row in rows:
        try:
            feat_dict = json.loads(row.features_json)
            vec = [float(feat_dict.get(col, 0.0)) for col in FEATURE_COLUMNS]
            label = LABEL_TO_INDEX.get(row.actual_result)
            if label is None:
                continue
            X_list.append(vec)
            y_list.append(label)
        except Exception as e:
            logger.debug(f"Skip id={row.id}: {e}")

    if len(X_list) < min_samples:
        logger.warning(f"Features valides insuffisantes ({len(X_list)}). Annulé.")
        return None

    X_raw = np.array(X_list, dtype=np.float32)
    y_all = np.array(y_list, dtype=np.int64)

    # Split chronologique 80/20
    n = len(X_raw)
    n_train = max(1, int(n * FEEDBACK_TRAIN_RATIO))
    X_train_raw, y_fb_train = X_raw[:n_train], y_all[:n_train]
    X_test_raw, y_fb_test = X_raw[n_train:], y_all[n_train:]

    logger.info(f"Feedback split — train: {n_train} | held-out: {n - n_train}")

    normalize = lambda X: (X - scaler_mean) / scaler_scale
    X_fb_train = normalize(X_train_raw)

    # Meta-features pour le feedback (NN+XGB+LGB chargés plus tard → on garde les raw ici,
    # les meta sont calculées après chargement des modèles et stockées dans le cache)
    # On stocke X_fb_train normalisé + X_fb_test normalisé et les labels
    X_fb_test = normalize(X_test_raw) if len(X_test_raw) > 0 else np.empty((0, X_fb_train.shape[1]), dtype=np.float32)

    result = {
        "X_fb_train": X_fb_train,
        "y_fb_train": y_fb_train,
        "X_fb_test": X_fb_test,
        "y_fb_test": y_fb_test,
    }

    # Sauvegarder les arrays bruts (sans meta-features — calculées séparément)
    _save_npz("feedback",
              X_fb_train=X_fb_train, y_fb_train=y_fb_train,
              X_fb_test=X_fb_test, y_fb_test=y_fb_test)
    cache_meta["feedback_count"] = verified_count
    _write_cache_meta(cache_meta)

    logger.info(f"[cache] Feedback sauvegardé ({n_train} train + {len(y_fb_test)} test).")
    return result


# ============================================================
# Cached: meta-features pour le feedback
# ============================================================

def get_feedback_meta(models, temperature, xgb_model, lgb_model,
                      X_fb_train, X_fb_test, verified_count, checkpoint_mtime) -> dict:
    """
    Meta-features du feedback, cachées séparément (dépendent du checkpoint ET du feedback count).
    """
    cache_meta = _read_cache_meta()
    fb_meta_key = f"fb_meta_{verified_count}_{checkpoint_mtime}"

    if cache_meta.get("fb_meta_key") == fb_meta_key:
        fb_meta_cache = _load_npz("feedback_meta")
        if fb_meta_cache is not None:
            logger.info("[cache] Meta-features feedback chargées depuis le cache.")
            return {
                "meta_fb_train": fb_meta_cache["meta_fb_train"],
                "meta_fb_test": fb_meta_cache["meta_fb_test"],
            }

    logger.info("[inférence] Calcul des meta-features feedback (NN + XGB + LGB)...")

    def _meta(X):
        if len(X) == 0:
            return np.empty((0, 12), dtype=np.float32)
        nn = get_nn_probs(models, X, temperature)
        xg = xgb_model.predict_proba(X)
        lg = lgb_model.predict(X)
        return build_meta_features(nn, xg, lg, X)

    meta_fb_train = _meta(X_fb_train)
    meta_fb_test = _meta(X_fb_test)

    _save_npz("feedback_meta", meta_fb_train=meta_fb_train, meta_fb_test=meta_fb_test)
    cache_meta["fb_meta_key"] = fb_meta_key
    _write_cache_meta(cache_meta)

    logger.info("[cache] Meta-features feedback sauvegardées.")
    return {"meta_fb_train": meta_fb_train, "meta_fb_test": meta_fb_test}


# ============================================================
# Point d'entrée principal
# ============================================================

def run_feedback_retrain(min_samples: int = MIN_FEEDBACK_SAMPLES) -> bool:
    logger.info("=" * 60)
    logger.info("FEEDBACK RETRAIN — split train/test honnête + cache")
    logger.info("=" * 60)

    if not MODEL_PATH.exists():
        logger.error("Checkpoint introuvable. Lancez d'abord un entraînement complet.")
        return False

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    session = get_session()

    try:
        models, temperature, scaler_params, xgb_model, lgb_model, old_meta = load_models(device)
        scaler_mean = np.array(scaler_params["mean"], dtype=np.float32)
        scaler_scale = np.array(scaler_params["scale"], dtype=np.float32)

        # Feedback (avec cache)
        fb = get_feedback_samples(session, min_samples, scaler_mean, scaler_scale)
        if fb is None:
            return False

        # Splits + meta val/test (avec cache)
        sd = get_splits_and_meta(session, models, temperature, xgb_model, lgb_model)

        # Meta-features feedback (avec cache, clé = checkpoint_mtime + feedback_count)
        verified_count = session.execute(
            select(func.count(PredictionLog.id)).where(
                PredictionLog.is_won.isnot(None),
                PredictionLog.features_json.isnot(None),
                PredictionLog.actual_result.isnot(None),
            )
        ).scalar() or 0

        fb_meta = get_feedback_meta(
            models, temperature, xgb_model, lgb_model,
            fb["X_fb_train"], fb["X_fb_test"],
            verified_count, _checkpoint_mtime(),
        )

        meta_val = sd["meta_val"]
        meta_test = sd["meta_test"]
        y_val = sd["y_val"]
        y_test = sd["y_test"]
        meta_fb_train = fb_meta["meta_fb_train"]
        meta_fb_test = fb_meta["meta_fb_test"]
        y_fb_train = fb["y_fb_train"]
        y_fb_test = fb["y_fb_test"]

        # Baseline : ancien méta-learner sur les sets held-out
        old_acc_test = float(np.mean(old_meta.predict(meta_test) == y_test))
        old_acc_fb = float(np.mean(old_meta.predict(meta_fb_test) == y_fb_test)) if len(y_fb_test) > 0 else None
        logger.info(f"Ancien méta-learner — test_orig: {old_acc_test:.3f}"
                    + (f" | feedback_test: {old_acc_fb:.3f}" if old_acc_fb is not None else ""))

        # Entraîner le nouveau méta-learner
        X_combined = np.vstack([meta_val] + [meta_fb_train] * FEEDBACK_WEIGHT)
        y_combined = np.concatenate([y_val] + [y_fb_train] * FEEDBACK_WEIGHT)

        logger.info(
            f"Dataset méta-learner — {len(meta_val)} val + "
            f"{len(meta_fb_train) * FEEDBACK_WEIGHT} feedback ({FEEDBACK_WEIGHT}x) "
            f"= {len(X_combined)} total"
        )

        new_meta = GradientBoostingClassifier(
            n_estimators=150, max_depth=3,
            learning_rate=0.08, subsample=0.8, random_state=42,
        )
        new_meta.fit(X_combined, y_combined)

        # Évaluation sur sets jamais vus pendant l'entraînement
        new_acc_test = float(np.mean(new_meta.predict(meta_test) == y_test))
        new_acc_fb = float(np.mean(new_meta.predict(meta_fb_test) == y_fb_test)) if len(y_fb_test) > 0 else None

        logger.info(f"Nouveau méta-learner — test_orig: {new_acc_test:.3f}"
                    + (f" | feedback_test (held-out): {new_acc_fb:.3f}" if new_acc_fb is not None else ""))
        logger.info(f"Delta test_orig: {new_acc_test - old_acc_test:+.3f}")

        # Garde-fou anti-régression
        if new_acc_test < old_acc_test + MIN_ACCURACY_DELTA:
            logger.warning(
                f"Régression ({new_acc_test:.3f} < {old_acc_test:.3f} - tolérance). "
                "Ancien modèle conservé."
            )
            return False

        with open(META_MODEL_PATH, "wb") as f:
            pickle.dump(new_meta, f)

        logger.info(
            f"Méta-learner sauvegardé. "
            f"Précision test : {old_acc_test:.3f} → {new_acc_test:.3f}"
        )
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur feedback retrain : {e}", exc_info=True)
        return False
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-samples", type=int, default=MIN_FEEDBACK_SAMPLES)
    parser.add_argument("--clear-cache", action="store_true", help="Supprime le cache avant de démarrer")
    args = parser.parse_args()

    if args.clear_cache:
        clear_cache()

    run_feedback_retrain(min_samples=args.min_samples)
