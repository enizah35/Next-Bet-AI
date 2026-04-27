"""
src/ingestion/api_football.py
Client API-Football (api-sports.io) pour les données de blessures en temps réel.

Usage : appeler get_team_injuries(team_name, league_id, season) avant chaque prédiction.
Les blessures ne sont PAS stockées en DB historique (données indisponibles rétrospectivement) :
elles servent uniquement d'ajustement à l'inférence.

Variables d'environnement requises :
  API_FOOTBALL_KEY = votre clé api-sports.io (gratuit : 100 req/jour)
"""

import logging
import os
from functools import lru_cache
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "")

# Mapping nom équipe DB → ID api-sports.io (compléter au besoin)
TEAM_ID_MAP: dict[str, int] = {
    # Premier League
    "Arsenal": 42, "Aston Villa": 66, "Bournemouth": 35, "Brentford": 55,
    "Brighton": 51, "Chelsea": 49, "Crystal Palace": 52, "Everton": 45,
    "Fulham": 36, "Ipswich": 57, "Leicester": 46, "Liverpool": 40,
    "Man City": 50, "Man United": 33, "Newcastle": 34, "Nottm Forest": 65,
    "Southampton": 41, "Tottenham": 47, "West Ham": 48, "Wolves": 39,
    # Ligue 1
    "Paris SG": 85, "Marseille": 81, "Lyon": 80, "Monaco": 91,
    "Lille": 79, "Nice": 84, "Rennes": 94, "Lens": 116,
    "Montpellier": 82, "Strasbourg": 95, "Toulouse": 96, "Nantes": 83,
    "Brest": 113, "Le Havre": 1100, "Reims": 93, "Saint-Etienne": 97,
    "Angers": 77, "Metz": 112,
    # Bundesliga
    "Bayern Munich": 157, "Borussia Dortmund": 165, "RB Leipzig": 173,
    "Bayer Leverkusen": 168, "Frankfurt": 169, "Stuttgart": 172,
    "Hoffenheim": 167, "Freiburg": 160, "Augsburg": 163, "Wolfsburg": 161,
    # La Liga
    "Real Madrid": 541, "Barcelona": 529, "Atletico Madrid": 530,
    "Sevilla": 536, "Real Sociedad": 548, "Real Betis": 543,
    "Villarreal": 533, "Valencia": 532, "Athletic Club": 531,
    # Serie A
    "Juventus": 496, "Inter": 505, "AC Milan": 489, "Napoli": 492,
    "Roma": 497, "Lazio": 487, "Atalanta": 499, "Fiorentina": 502,
}

# Mapping ligue DB → ID api-sports.io + saison courante
LEAGUE_ID_MAP: dict[str, int] = {
    "Premier League": 39,
    "Ligue 1": 61,
    "Bundesliga": 78,
    "La Liga": 140,
    "Serie A": 135,
    "Championship": 40,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Süper Lig": 203,
}


def _headers() -> dict:
    return {"x-apisports-key": API_KEY}


@lru_cache(maxsize=512)
def get_team_injuries(team_id: int, league_id: int, season: int) -> int:
    """
    Retourne le nombre de joueurs blessés/suspendus pour une équipe
    avant le prochain match. Met en cache les résultats.

    Retourne 0 si API_FOOTBALL_KEY absent ou erreur réseau.
    """
    if not API_KEY:
        return 0

    try:
        r = requests.get(
            f"{API_BASE}/injuries",
            headers=_headers(),
            params={"team": team_id, "league": league_id, "season": season},
            timeout=5,
        )
        data = r.json()
        injuries = data.get("response", [])
        # Filtrer : seulement blessés / suspendus (pas "questionable")
        active = [
            p for p in injuries
            if p.get("player", {}).get("type") in ("injured", "suspended")
        ]
        return len(active)
    except Exception as e:
        logger.warning(f"API-Football error (team={team_id}): {e}")
        return 0


def get_injuries_for_match(
    home_team: str,
    away_team: str,
    league: str,
    season: int,
) -> tuple[int, int]:
    """
    Retourne (home_injuries, away_injuries) pour un match donné.
    Utilise TEAM_ID_MAP et LEAGUE_ID_MAP.
    """
    league_id = LEAGUE_ID_MAP.get(league, 0)
    if league_id == 0:
        return 0, 0

    home_id = TEAM_ID_MAP.get(home_team, 0)
    away_id = TEAM_ID_MAP.get(away_team, 0)

    home_inj = get_team_injuries(home_id, league_id, season) if home_id else 0
    away_inj = get_team_injuries(away_id, league_id, season) if away_id else 0

    return home_inj, away_inj


def injury_adjustment(home_injuries: int, away_injuries: int) -> dict[str, float]:
    """
    Calcule un ajustement des probabilités basé sur le différentiel de blessures.
    Chaque blessure = -1.5% sur la probabilité de victoire de l'équipe touchée.
    Capped à ±10%.
    """
    delta = (away_injuries - home_injuries) * 0.015  # positif = avantage home
    delta = max(-0.10, min(0.10, delta))
    return {"home_adj": round(delta, 4), "away_adj": round(-delta, 4)}


def clear_injury_cache() -> None:
    """Vide le cache LRU (à appeler en début de journée)."""
    get_team_injuries.cache_clear()
