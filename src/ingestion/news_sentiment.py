"""
src/ingestion/news_sentiment.py
Module d'analyse de sentiment basé sur les actualités football (RSS multi-sources).
Produit un score de sentiment par équipe [-1.0, +1.0] utilisé pour ajuster
les probabilités du modèle à l'inférence.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import feedparser

logger = logging.getLogger(__name__)

# ============================================================
# Sources RSS par ligue (diversifiées pour meilleure couverture)
# ============================================================
RSS_SOURCES: dict[str, list[dict]] = {
    "Premier League": [
        {"url": "http://feeds.bbci.co.uk/sport/football/rss.xml", "lang": "en", "name": "BBC Sport"},
        {"url": "https://www.skysports.com/rss/12040", "lang": "en", "name": "Sky Sports PL"},
        {"url": "https://www.theguardian.com/football/premierleague/rss", "lang": "en", "name": "Guardian PL"},
    ],
    "Ligue 1": [
        {"url": "https://rmcsport.bfmtv.com/rss/football/", "lang": "fr", "name": "RMC Sport"},
        {"url": "https://www.lequipe.fr/rss/actu_rss_Football.xml", "lang": "fr", "name": "L'Equipe"},
    ],
}

# ============================================================
# Dictionnaires de mots-clés pondérés (EN / FR)
# ============================================================
NEGATIVE_KEYWORDS: dict[str, float] = {
    # Blessures / Absences (fort impact)
    "injury": -0.8, "injured": -0.8, "blessure": -0.8, "blessé": -0.8,
    "out for": -0.9, "sidelined": -0.7, "ruled out": -0.9, "absent": -0.7,
    "forfait": -0.8, "indisponible": -0.7, "miss": -0.5, "doubt": -0.4,
    "incertain": -0.4, "touché": -0.5,
    # Suspensions
    "suspended": -0.7, "suspendu": -0.7, "red card": -0.6, "carton rouge": -0.6,
    "ban": -0.6, "suspension": -0.6,
    # Crise / Problèmes internes
    "sacked": -0.6, "viré": -0.6, "crisis": -0.5, "crise": -0.5,
    "unrest": -0.4, "tension": -0.3, "conflict": -0.4, "conflit": -0.4,
    # Mauvais résultats
    "defeat": -0.3, "défaite": -0.3, "loss": -0.2, "losing streak": -0.5,
    "humiliated": -0.4, "humiliation": -0.4, "thrashed": -0.4, "éliminé": -0.3,
}

POSITIVE_KEYWORDS: dict[str, float] = {
    # Retours / Renforts
    "return": 0.5, "retour": 0.5, "back in training": 0.6, "reprise": 0.5,
    "fit": 0.4, "apte": 0.4, "available": 0.3, "disponible": 0.3,
    "signing": 0.5, "recrue": 0.5, "transfer": 0.3, "transfert": 0.3,
    # Bons résultats / Forme
    "win": 0.3, "victoire": 0.3, "winning streak": 0.6, "série": 0.3,
    "unbeaten": 0.5, "invaincu": 0.5, "top form": 0.5, "en forme": 0.4,
    "impressive": 0.3, "dominant": 0.3, "clinical": 0.3,
    # Confiance / Motivation
    "boost": 0.4, "confident": 0.3, "confiance": 0.3, "motivated": 0.3,
    "record": 0.3, "historic": 0.3, "historique": 0.3,
}

# ============================================================
# Alias de noms d'équipe pour le matching RSS
# ============================================================
TEAM_ALIASES: dict[str, list[str]] = {
    # Premier League
    "Arsenal": ["arsenal", "gunners"],
    "Man City": ["man city", "manchester city", "citizens", "city"],
    "Liverpool": ["liverpool", "reds"],
    "Chelsea": ["chelsea", "blues"],
    "Tottenham": ["tottenham", "spurs"],
    "Man United": ["man united", "manchester united", "man utd", "red devils"],
    "Newcastle": ["newcastle", "magpies"],
    "Aston Villa": ["aston villa", "villa"],
    "Brighton": ["brighton", "seagulls"],
    "West Ham": ["west ham", "hammers"],
    "Bournemouth": ["bournemouth", "cherries"],
    "Crystal Palace": ["crystal palace", "palace", "eagles"],
    "Fulham": ["fulham", "cottagers"],
    "Wolves": ["wolves", "wolverhampton"],
    "Everton": ["everton", "toffees"],
    "Brentford": ["brentford", "bees"],
    "Nott'm Forest": ["nottingham forest", "forest", "nott"],
    "Luton": ["luton", "hatters"],
    "Burnley": ["burnley", "clarets"],
    "Sheffield United": ["sheffield united", "blades"],
    # Ligue 1
    "Paris SG": ["paris", "psg", "paris sg", "paris saint-germain", "parisiens"],
    "Marseille": ["marseille", "om", "olympique de marseille", "phocéens"],
    "Lyon": ["lyon", "ol", "olympique lyonnais"],
    "Monaco": ["monaco", "asm"],
    "Lille": ["lille", "losc"],
    "Rennes": ["rennes", "stade rennais"],
    "Nice": ["nice", "ogc nice"],
    "Lens": ["lens", "rc lens", "sang et or"],
    "Strasbourg": ["strasbourg", "racing"],
    "Nantes": ["nantes", "fcn", "canaris"],
    "Toulouse": ["toulouse", "tfc"],
    "Montpellier": ["montpellier", "mhsc"],
    "Reims": ["reims", "stade de reims"],
    "Brest": ["brest", "stade brestois"],
    "Le Havre": ["le havre", "hac"],
    "Metz": ["metz", "fc metz"],
    "Clermont": ["clermont", "clermont foot"],
    "Lorient": ["lorient", "fc lorient"],
}


@dataclass
class TeamSentiment:
    """Résultat de l'analyse de sentiment pour une équipe."""
    team_name: str
    score: float = 0.0  # [-1.0, +1.0]
    positive_count: int = 0
    negative_count: int = 0
    articles_matched: int = 0
    headlines: list[str] = field(default_factory=list)


def _team_mentioned(title_lower: str, team_name: str) -> bool:
    """Vérifie si une équipe est mentionnée dans un titre (nom exact + alias)."""
    # Nom exact
    if team_name.lower() in title_lower:
        return True
    # Alias
    aliases = TEAM_ALIASES.get(team_name, [])
    for alias in aliases:
        # Utiliser word boundary pour éviter les faux positifs (ex: "Nice" dans "nice goal")
        if len(alias) <= 4:
            # Pour les alias courts, exiger un word boundary
            if re.search(rf'\b{re.escape(alias)}\b', title_lower):
                return True
        else:
            if alias in title_lower:
                return True
    return False


def _score_headline(title: str) -> float:
    """Calcule le score de sentiment d'un titre d'article."""
    title_lower = title.lower()
    score = 0.0
    matched = False

    for kw, weight in NEGATIVE_KEYWORDS.items():
        if kw in title_lower:
            score += weight
            matched = True

    for kw, weight in POSITIVE_KEYWORDS.items():
        if kw in title_lower:
            score += weight
            matched = True

    # Si aucun mot-clé, score neutre
    if not matched:
        return 0.0

    # Clamp entre -1 et 1
    return max(-1.0, min(1.0, score))


def fetch_rss_entries(league: str, max_entries: int = 30) -> list[dict]:
    """Récupère les entrées RSS de toutes les sources pour une ligue donnée."""
    sources = RSS_SOURCES.get(league, [])
    all_entries = []

    for source in sources:
        try:
            feed = feedparser.parse(source["url"])
            for entry in feed.entries[:max_entries]:
                all_entries.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "source": source["name"],
                    "lang": source["lang"],
                })
        except Exception as e:
            logger.warning(f"Erreur RSS {source['name']}: {e}")

    logger.info(f"RSS: {len(all_entries)} articles récupérés pour {league}")
    return all_entries


def analyze_team_sentiment(
    team_name: str,
    entries: list[dict],
    max_headlines: int = 5,
) -> TeamSentiment:
    """Analyse le sentiment des news pour une équipe spécifique."""
    result = TeamSentiment(team_name=team_name)

    for entry in entries:
        title = entry["title"]
        title_lower = title.lower()

        if not _team_mentioned(title_lower, team_name):
            continue

        result.articles_matched += 1
        headline_score = _score_headline(title)

        if headline_score < 0:
            result.negative_count += 1
        elif headline_score > 0:
            result.positive_count += 1

        result.score += headline_score

        if len(result.headlines) < max_headlines:
            result.headlines.append(title)

    # Normaliser le score si on a plusieurs articles (moyenne pondérée)
    if result.articles_matched > 0:
        result.score = result.score / result.articles_matched
        # Clamp final
        result.score = max(-1.0, min(1.0, result.score))

    return result


def get_match_sentiment(
    home_team: str,
    away_team: str,
    league: str,
    entries: Optional[list[dict]] = None,
) -> dict:
    """
    Calcule le sentiment pour les deux équipes d'un match.

    Returns:
        dict avec home_sentiment, away_sentiment, sentiment_diff, et détails
    """
    if entries is None:
        entries = fetch_rss_entries(league)

    home_sent = analyze_team_sentiment(home_team, entries)
    away_sent = analyze_team_sentiment(away_team, entries)

    return {
        "home_sentiment": round(home_sent.score, 3),
        "away_sentiment": round(away_sent.score, 3),
        "sentiment_diff": round(home_sent.score - away_sent.score, 3),
        "home_headlines": home_sent.headlines,
        "away_headlines": away_sent.headlines,
        "home_articles": home_sent.articles_matched,
        "away_articles": away_sent.articles_matched,
        "home_positive": home_sent.positive_count,
        "home_negative": home_sent.negative_count,
        "away_positive": away_sent.positive_count,
        "away_negative": away_sent.negative_count,
    }


def adjust_probabilities(
    probs: dict[str, float],
    home_sentiment: float,
    away_sentiment: float,
    strength: float = 0.08,
) -> dict[str, float]:
    """
    Ajuste les probabilités du modèle en fonction du sentiment.

    Le sentiment agit comme un multiplicateur léger :
    - Sentiment positif home → boost p(H), léger baisse p(A)
    - Sentiment négatif home → baisse p(H), léger boost p(A)
    - strength contrôle l'amplitude max de l'ajustement (défaut 8%)

    Args:
        probs: {"home_win": float, "draw": float, "away_win": float}
        home_sentiment: score [-1, 1]
        away_sentiment: score [-1, 1]
        strength: amplitude max de l'ajustement

    Returns:
        Probabilités ajustées (toujours normalisées à 1.0)
    """
    p_h = probs["home_win"]
    p_d = probs["draw"]
    p_a = probs["away_win"]

    # Calcul du shift net (différence de sentiment)
    net_sentiment = home_sentiment - away_sentiment  # [-2, +2]

    # Ajustement proportionnel
    shift = net_sentiment * strength * 0.5  # max ±strength

    p_h_adj = p_h + shift
    p_a_adj = p_a - shift
    # Le draw absorbe la différence restante si les ajustements créent des anomalies
    p_d_adj = p_d

    # Clamp pour éviter des probabilités négatives
    p_h_adj = max(0.02, p_h_adj)
    p_a_adj = max(0.02, p_a_adj)
    p_d_adj = max(0.02, p_d_adj)

    # Re-normaliser pour sommer à 1.0
    total = p_h_adj + p_d_adj + p_a_adj
    return {
        "home_win": round(p_h_adj / total, 4),
        "draw": round(p_d_adj / total, 4),
        "away_win": round(p_a_adj / total, 4),
    }
