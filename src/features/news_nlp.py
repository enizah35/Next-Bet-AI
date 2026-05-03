"""
src/features/news_nlp.py
Analyse de sentiment des news pré-match via transformers (DistilBERT multilingue).

Le modèle est téléchargé automatiquement par HuggingFace au premier appel (~250 MB)
et mis en cache dans ~/.cache/huggingface/. Les résultats par équipe/date sont
mis en cache dans un fichier JSON local pour éviter de re-inférer à chaque appel API.

Retourne un score [-1, +1] par équipe :
  +1 → très positif (retour de blessé, victoires récentes, moral au beau fixe)
  -1 → très négatif (blessures, suspension, vestiaire en crise)
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent.parent / "scripts" / "news_sentiment_cache.json"

_BERT_PIPELINE = None
_BERT_PIPELINE_FAILED = False


def _get_bert_pipeline():
    """Charge le pipeline BERT une seule fois (singleton process-wide)."""
    global _BERT_PIPELINE, _BERT_PIPELINE_FAILED
    if _BERT_PIPELINE is not None or _BERT_PIPELINE_FAILED:
        return _BERT_PIPELINE
    try:
        from transformers import pipeline as hf_pipeline
        model_name = "lxyuan/distilbert-base-multilingual-cased-sentiments-student"
        _BERT_PIPELINE = hf_pipeline("text-classification", model=model_name, top_k=1)
        logger.info("Pipeline BERT (sentiment) chargé une fois (singleton).")
    except ImportError:
        _BERT_PIPELINE_FAILED = True
        logger.warning("transformers non installé — sentiment BERT désactivé.")
    except Exception as e:
        _BERT_PIPELINE_FAILED = True
        logger.warning(f"BERT pipeline init échouée: {e}")
    return _BERT_PIPELINE

# Mots-clés football pour enrichir le signal BERT avec du contexte métier
NEGATIVE_SIGNALS = [
    # FR
    "blessé", "blessure", "forfait", "absent", "indisponible", "suspendu",
    "suspension", "carton rouge", "opération", "rechute", "crise", "viré",
    "licencié", "démissionné", "défaite", "désastre", "mauvaise passe",
    # EN
    "injured", "injury", "doubt", "out", "sidelined", "suspended", "crisis",
    "sacked", "fired", "resigned", "knocked out", "rift", "fallout",
]
POSITIVE_SIGNALS = [
    # FR
    "retour", "rétabli", "disponible", "convoqué", "victoire", "confiant",
    "en forme", "bon état", "récupéré", "renforcé",
    # EN
    "return", "fit", "back", "available", "selected", "confident", "strong",
    "recovered", "good form", "ready",
]


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _keyword_score(text: str) -> float:
    """Score rapide basé sur les mots-clés football, en complément de BERT."""
    text_lower = text.lower()
    neg = sum(1 for kw in NEGATIVE_SIGNALS if kw in text_lower)
    pos = sum(1 for kw in POSITIVE_SIGNALS if kw in text_lower)
    total = neg + pos
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _bert_score(texts: list[str], pipeline) -> float:
    """Moyenne des scores BERT sur une liste de textes. Retourne [-1, +1]."""
    if not texts:
        return 0.0
    try:
        results = pipeline(texts, truncation=True, max_length=128, batch_size=8)
        scores = []
        for r in results:
            label = r["label"].upper()
            score = r["score"]
            if "POSITIVE" in label or label in ("5 STARS", "4 STARS"):
                scores.append(score)
            elif "NEGATIVE" in label or label in ("1 STAR", "2 STARS"):
                scores.append(-score)
            else:
                scores.append(0.0)
        return float(sum(scores) / len(scores))
    except Exception as e:
        logger.debug(f"BERT inference error: {e}")
        return 0.0


def get_team_news_sentiment(
    team_name: str,
    headlines: list[str],
    use_bert: bool = True,
) -> float:
    """
    Retourne un score de sentiment [-1, +1] pour une équipe à partir
    de ses titres d'actualité du jour.

    Le score combine :
    - Mots-clés métier football (rapide, langue FR+EN)
    - Inférence BERT multilingue (si use_bert=True et modèle disponible)
    """
    if not headlines:
        return 0.0

    today_key = f"{team_name}_{date.today().isoformat()}"
    cache = _load_cache()

    if today_key in cache:
        return float(cache[today_key])

    # Score mots-clés (toujours disponible)
    kw_scores = [_keyword_score(h) for h in headlines]
    kw_mean = sum(kw_scores) / len(kw_scores) if kw_scores else 0.0

    bert_mean = 0.0
    if use_bert:
        pipe = _get_bert_pipeline()
        if pipe is not None:
            try:
                bert_mean = _bert_score(headlines, pipe)
                logger.debug(f"BERT sentiment {team_name}: {bert_mean:.3f}")
            except Exception as e:
                logger.warning(f"BERT indisponible pour {team_name}: {e}")

    # Combinaison : BERT pondéré à 70% si disponible, mots-clés à 30%
    if bert_mean != 0.0:
        final = 0.7 * bert_mean + 0.3 * kw_mean
    else:
        final = kw_mean

    final = max(-1.0, min(1.0, final))
    cache[today_key] = round(final, 4)
    _save_cache(cache)

    return final


def compute_news_adjustment(
    home_sentiment: float,
    away_sentiment: float,
    max_shift: float = 0.04,
) -> dict[str, float]:
    """
    Convertit les scores de sentiment en ajustements de probabilités.

    Un sentiment très négatif pour l'équipe domicile (−1) peut réduire
    sa probabilité de victoire de max max_shift points.

    Retourne des deltas à appliquer : {"home": Δ, "draw": Δ, "away": Δ}
    """
    # Sentiment net : positif pour dom = favorable, négatif pour ext = favorable dom
    net = home_sentiment - away_sentiment  # [-2, +2]
    shift = net * max_shift / 2.0          # [-max_shift, +max_shift]

    return {
        "home": round(shift, 4),
        "draw": round(-abs(shift) * 0.3, 4),   # nul légèrement pénalisé si signal fort
        "away": round(-shift, 4),
    }
