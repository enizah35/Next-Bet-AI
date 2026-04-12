"""
src/ingestion/live_odds.py
Module de récupération des cotes live via The Odds API.
Fournit les probabilités implicites réelles du marché pour chaque match.
Clé API gratuite : https://the-odds-api.com/ (500 req/mois)
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ============================================================
# Configuration
# ============================================================
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

# Mapping des ligues vers les clés The Odds API
LEAGUE_KEYS = {
    "Premier League": "soccer_epl",
    "Ligue 1": "soccer_france_ligue_one",
}

# Alias pour matcher les noms ESPN/DB → noms The Odds API
TEAM_NAME_MAP = {
    # Premier League
    "Arsenal": ["Arsenal"],
    "Man City": ["Manchester City"],
    "Liverpool": ["Liverpool"],
    "Chelsea": ["Chelsea"],
    "Tottenham": ["Tottenham Hotspur", "Tottenham"],
    "Man United": ["Manchester United"],
    "Newcastle": ["Newcastle United", "Newcastle"],
    "Aston Villa": ["Aston Villa"],
    "Brighton": ["Brighton and Hove Albion", "Brighton"],
    "West Ham": ["West Ham United", "West Ham"],
    "Bournemouth": ["AFC Bournemouth", "Bournemouth"],
    "Crystal Palace": ["Crystal Palace"],
    "Fulham": ["Fulham"],
    "Wolves": ["Wolverhampton Wanderers", "Wolverhampton", "Wolves"],
    "Everton": ["Everton"],
    "Brentford": ["Brentford"],
    "Nott'm Forest": ["Nottingham Forest"],
    "Luton": ["Luton Town", "Luton"],
    "Burnley": ["Burnley"],
    "Sheffield United": ["Sheffield United", "Sheffield Utd"],
    "Leicester": ["Leicester City", "Leicester"],
    "Ipswich": ["Ipswich Town", "Ipswich"],
    "Southampton": ["Southampton"],
    # Ligue 1
    "Paris SG": ["Paris Saint-Germain", "Paris Saint Germain", "PSG"],
    "Marseille": ["Olympique de Marseille", "Marseille"],
    "Lyon": ["Olympique Lyonnais", "Lyon"],
    "Monaco": ["AS Monaco", "Monaco"],
    "Lille": ["Lille OSC", "Lille"],
    "Rennes": ["Stade Rennais", "Rennes"],
    "Nice": ["OGC Nice", "Nice"],
    "Lens": ["RC Lens", "Lens"],
    "Strasbourg": ["RC Strasbourg Alsace", "Strasbourg"],
    "Nantes": ["FC Nantes", "Nantes"],
    "Toulouse": ["Toulouse FC", "Toulouse"],
    "Montpellier": ["Montpellier HSC", "Montpellier"],
    "Reims": ["Stade de Reims", "Reims"],
    "Brest": ["Stade Brestois 29", "Brest"],
    "Le Havre": ["Le Havre AC", "Le Havre"],
    "Metz": ["FC Metz", "Metz"],
    "Clermont": ["Clermont Foot", "Clermont"],
    "Lorient": ["FC Lorient", "Lorient"],
    "St Etienne": ["AS Saint-Étienne", "Saint-Etienne", "St Etienne"],
    "Angers": ["Angers SCO", "Angers"],
    "Auxerre": ["AJ Auxerre", "Auxerre"],
}

# Inverse map: odds API name → our DB name
_REVERSE_MAP: dict[str, str] = {}
for db_name, api_names in TEAM_NAME_MAP.items():
    for api_name in api_names:
        _REVERSE_MAP[api_name.lower()] = db_name


def _normalize_team(odds_api_name: str) -> str:
    """Convertit un nom The Odds API vers notre nom DB."""
    return _REVERSE_MAP.get(odds_api_name.lower(), odds_api_name)


def fetch_live_odds(league: str) -> dict[tuple[str, str], dict]:
    """
    Récupère les cotes h2h des bookmakers pour une ligue.

    Returns:
        dict[(home_db_name, away_db_name)] → {
            "avg_h": float, "avg_d": float, "avg_a": float,
            "implied_home": float, "implied_draw": float, "implied_away": float,
            "bookmakers_count": int, "best_odds": {...}
        }
    """
    sport_key = LEAGUE_KEYS.get(league)
    if not sport_key:
        logger.warning(f"Ligue non supportée pour les cotes: {league}")
        return {}

    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY non configurée — cotes live désactivées")
        return {}

    url = f"{ODDS_API_BASE}/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 401:
            logger.error("ODDS_API_KEY invalide (401)")
            return {}
        if resp.status_code == 429:
            logger.warning("Quota The Odds API atteint (429)")
            return {}
        resp.raise_for_status()

        # Quota remaining
        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(f"The Odds API — requêtes restantes ce mois: {remaining}")

        data = resp.json()
    except Exception as e:
        logger.error(f"Erreur appel The Odds API: {e}")
        return {}

    results: dict[tuple[str, str], dict] = {}

    for event in data:
        home_api = event.get("home_team", "")
        away_api = event.get("away_team", "")
        home_db = _normalize_team(home_api)
        away_db = _normalize_team(away_api)

        # Collecter toutes les cotes des bookmakers
        all_h, all_d, all_a = [], [], []
        best_h, best_d, best_a = 0.0, 0.0, 0.0

        for bm in event.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                h = outcomes.get(home_api, 0)
                d = outcomes.get("Draw", 0)
                a = outcomes.get(away_api, 0)
                if h > 0 and d > 0 and a > 0:
                    all_h.append(h)
                    all_d.append(d)
                    all_a.append(a)
                    best_h = max(best_h, h)
                    best_d = max(best_d, d)
                    best_a = max(best_a, a)

        if not all_h:
            continue

        avg_h = sum(all_h) / len(all_h)
        avg_d = sum(all_d) / len(all_d)
        avg_a = sum(all_a) / len(all_a)

        # Probabilités implicites (margin-adjusted)
        margin = (1.0 / avg_h) + (1.0 / avg_d) + (1.0 / avg_a)
        implied_home = (1.0 / avg_h) / margin
        implied_draw = (1.0 / avg_d) / margin
        implied_away = (1.0 / avg_a) / margin

        results[(home_db, away_db)] = {
            "avg_h": round(avg_h, 2),
            "avg_d": round(avg_d, 2),
            "avg_a": round(avg_a, 2),
            "implied_home": round(implied_home, 4),
            "implied_draw": round(implied_draw, 4),
            "implied_away": round(implied_away, 4),
            "bookmakers_count": len(all_h),
            "best_odds": {
                "home": round(best_h, 2),
                "draw": round(best_d, 2),
                "away": round(best_a, 2),
            },
        }

    logger.info(f"Cotes live: {len(results)} matchs récupérés pour {league}")
    return results


def get_match_odds(
    home_team: str,
    away_team: str,
    odds_cache: dict,
) -> Optional[dict]:
    """
    Cherche les cotes d'un match dans le cache.
    Essaie le match exact et aussi l'inversé (au cas où).
    """
    # Match exact
    result = odds_cache.get((home_team, away_team))
    if result:
        return result

    # Essayer tous les matchs du cache pour un matching fuzzy
    for (h, a), data in odds_cache.items():
        if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
           (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
            return data

    return None


# ============================================================
# Multi-market : cotes Winamax & Betclic (h2h, totals, btts)
# ============================================================
BROKER_KEYS = ["winamax", "betclic"]
BROKER_DISPLAY = {"winamax": "Winamax", "betclic": "Betclic"}


def fetch_bookmaker_odds(league: str) -> dict[tuple[str, str], dict]:
    """
    Récupère les cotes multi-marchés de Winamax & Betclic via The Odds API.
    Marchés : h2h (1X2), totals (Over/Under), btts (Les deux marquent).

    Returns:
        dict[(home_db, away_db)] → {
            "h2h": { "winamax": {"home": x, "draw": x, "away": x}, "betclic": {...} },
            "totals": { "winamax": [{"point": 2.5, "over": x, "under": x}, ...], ... },
            "btts": { "winamax": {"yes": x, "no": x}, "betclic": {...} },
        }
    """
    sport_key = LEAGUE_KEYS.get(league)
    if not sport_key:
        return {}
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY non configurée — cotes bookmaker désactivées")
        return {}

    url = f"{ODDS_API_BASE}/{sport_key}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h,totals,btts",
        "oddsFormat": "decimal",
        "bookmakers": ",".join(BROKER_KEYS),
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code in (401, 429):
            logger.warning(f"The Odds API erreur {resp.status_code}")
            return {}
        resp.raise_for_status()
        remaining = resp.headers.get("x-requests-remaining", "?")
        logger.info(f"The Odds API (multi-market) — requêtes restantes: {remaining}")
        data = resp.json()
    except Exception as e:
        logger.error(f"Erreur The Odds API multi-market: {e}")
        return {}

    results: dict[tuple[str, str], dict] = {}

    for event in data:
        home_api = event.get("home_team", "")
        away_api = event.get("away_team", "")
        home_db = _normalize_team(home_api)
        away_db = _normalize_team(away_api)

        match_data: dict = {"h2h": {}, "totals": {}, "btts": {}}

        for bm in event.get("bookmakers", []):
            bm_key = bm.get("key", "")
            if bm_key not in BROKER_KEYS:
                continue
            bm_name = BROKER_DISPLAY.get(bm_key, bm_key)

            for market in bm.get("markets", []):
                mkey = market.get("key", "")
                outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}

                if mkey == "h2h":
                    h = outcomes.get(home_api, 0)
                    d = outcomes.get("Draw", 0)
                    a = outcomes.get(away_api, 0)
                    if h > 0 and d > 0 and a > 0:
                        match_data["h2h"][bm_name] = {
                            "home": round(h, 2),
                            "draw": round(d, 2),
                            "away": round(a, 2),
                        }

                elif mkey == "totals":
                    lines: list[dict] = []
                    # Group by point value
                    over_map: dict[float, float] = {}
                    under_map: dict[float, float] = {}
                    for o in market.get("outcomes", []):
                        pt = o.get("point", 0)
                        if o["name"] == "Over":
                            over_map[pt] = o["price"]
                        elif o["name"] == "Under":
                            under_map[pt] = o["price"]
                    for pt in sorted(set(list(over_map.keys()) + list(under_map.keys()))):
                        if pt in over_map and pt in under_map:
                            lines.append({
                                "point": pt,
                                "over": round(over_map[pt], 2),
                                "under": round(under_map[pt], 2),
                            })
                    if lines:
                        match_data["totals"][bm_name] = lines

                elif mkey == "btts":
                    yes = outcomes.get("Yes", 0)
                    no = outcomes.get("No", 0)
                    if yes > 0 and no > 0:
                        match_data["btts"][bm_name] = {
                            "yes": round(yes, 2),
                            "no": round(no, 2),
                        }

        # Ne garder que si au moins un bookmaker a des données
        if any(match_data[k] for k in match_data):
            results[(home_db, away_db)] = match_data

    logger.info(f"Cotes bookmaker multi-market: {len(results)} matchs pour {league}")
    return results


def get_match_bookmaker_odds(
    home_team: str,
    away_team: str,
    bookmaker_cache: dict,
) -> Optional[dict]:
    """Cherche les cotes bookmaker d'un match dans le cache (fuzzy)."""
    result = bookmaker_cache.get((home_team, away_team))
    if result:
        return result
    for (h, a), data in bookmaker_cache.items():
        if (home_team.lower() in h.lower() or h.lower() in home_team.lower()) and \
           (away_team.lower() in a.lower() or a.lower() in away_team.lower()):
            return data
    return None
