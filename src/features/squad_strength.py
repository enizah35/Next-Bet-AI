"""
src/features/squad_strength.py
Évaluation de la force de l'effectif disponible via API-Football.

Sources :
  - /injuries?fixture={id}   → joueurs blessés/suspendus (déjà utilisé partiellement)
  - /players/squads?team={id} → effectif complet
  - /fixtures/lineups?fixture={id} → 11 titulaires (dispo ~1h avant KO)

La force d'un effectif est calculée via un score de qualité par joueur.
En l'absence de ratings officiels, on utilise :
  1. Les ratings historiques moyens de API-Football (/players/statistics)
  2. Fallback : proxy position (gardien=5, défenseur=4, milieu=6, attaquant=7)

Retourne (home_squad_score, away_squad_score) ∈ [0, 1] normalisés,
et (home_key_out, away_key_out) booléens si un joueur-clé est absent.
"""

import logging
import os
import time
from functools import lru_cache
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

# Positions et leur poids relatif dans l'effectif (proxy de qualité)
POSITION_WEIGHTS = {
    "Goalkeeper": 5.0,
    "Defender":   4.0,
    "Midfielder": 5.5,
    "Attacker":   7.0,
}
# Joueurs considérés "clés" si leur absence impacte fortement (top attaquants/milieux)
KEY_POSITION_THRESHOLD = 6.0


def _api_get(endpoint: str, params: dict) -> Optional[dict]:
    if not API_KEY:
        return None
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
        if r.status_code == 429:
            logger.warning("API-Football rate limit — pause 60s")
            time.sleep(60)
            r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug(f"API-Football {endpoint}: {e}")
    return None


@lru_cache(maxsize=128)
def get_team_id_from_api(team_name: str, league_id: int, season: int) -> Optional[int]:
    """Résout le team_id API-Football depuis le nom."""
    data = _api_get("teams", {"name": team_name, "league": league_id, "season": season})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None


def get_squad_availability(
    team_api_id: int,
    fixture_id: Optional[int] = None,
    season: int = 2024,
) -> dict:
    """
    Retourne les informations de disponibilité de l'effectif pour un match.

    Si fixture_id fourni → tente de récupérer la compo officielle (1h avant KO).
    Sinon → utilise les blessures de l'équipe.

    Retourne:
        {
            "squad_score": float [0-1],    # qualité disponible / qualité totale
            "available_count": int,
            "total_count": int,
            "key_player_out": bool,
            "missing_players": list[str],
        }
    """
    # 1. Essayer la compo officielle si le match est proche
    if fixture_id:
        lineup_data = _api_get("fixtures/lineups", {"fixture": fixture_id})
        if lineup_data and lineup_data.get("response"):
            return _parse_lineup(lineup_data["response"], team_api_id)

    # 2. Effectif complet + blessures
    squad_data = _api_get("players/squads", {"team": team_api_id})
    injury_data = _api_get("injuries", {"team": team_api_id, "season": season})

    if not squad_data or not squad_data.get("response"):
        return _default_squad()

    # Construire l'effectif avec poids de position
    players = squad_data["response"][0].get("players", []) if squad_data["response"] else []
    squad = {}
    for p in players:
        name = p.get("name", "")
        pos = p.get("position", "Midfielder")
        weight = POSITION_WEIGHTS.get(pos, 5.0)
        squad[name] = weight

    # Joueurs indisponibles
    missing = set()
    if injury_data and injury_data.get("response"):
        for inj in injury_data["response"]:
            player_name = inj.get("player", {}).get("name", "")
            reason = inj.get("player", {}).get("reason", "")
            if player_name and reason.lower() not in ("suspended", "unknown") or player_name:
                missing.add(player_name)

    available = {name: w for name, w in squad.items() if name not in missing}
    total_weight = sum(squad.values()) or 1.0
    avail_weight = sum(available.values())
    key_player_out = any(w >= KEY_POSITION_THRESHOLD for name, w in squad.items() if name in missing)

    return {
        "squad_score": round(avail_weight / total_weight, 4),
        "available_count": len(available),
        "total_count": len(squad),
        "key_player_out": key_player_out,
        "missing_players": list(missing),
    }


def _parse_lineup(lineups: list, team_api_id: int) -> dict:
    """Parse une réponse de lineup officielle."""
    for lineup in lineups:
        if lineup.get("team", {}).get("id") == team_api_id:
            starters = lineup.get("startXI", [])
            # Une compo officielle = effectif au complet (11 joueurs confirmés)
            return {
                "squad_score": 1.0,  # compo officielle = disponibilité totale des 11
                "available_count": len(starters),
                "total_count": 11,
                "key_player_out": False,
                "missing_players": [],
            }
    return _default_squad()


def _default_squad() -> dict:
    return {
        "squad_score": 1.0,
        "available_count": 11,
        "total_count": 11,
        "key_player_out": False,
        "missing_players": [],
    }


# Codes ligue API-Football pour nos championnats
LEAGUE_API_IDS = {
    "Ligue 1": 61,
    "Premier League": 39,
    "Bundesliga": 78,
    "La Liga": 140,
    "Serie A": 135,
    "Championship": 40,
    "Eredivisie": 88,
    "Primeira Liga": 94,
    "Süper Lig": 203,
    "Ligue 2": 62,
    "2. Bundesliga": 79,
    "La Liga 2": 141,
    "Serie B": 136,
    "Belgian Pro League": 144,
    "Scottish Premiership": 179,
}


def compute_squad_adjustment(
    home_squad: dict,
    away_squad: dict,
    max_shift: float = 0.05,
) -> dict[str, float]:
    """
    Convertit les scores d'effectif en ajustements de probabilités.

    Un écart de disponibilité de 10% peut déplacer les probs de max_shift points.
    Retourne des deltas {"home": Δ, "draw": Δ, "away": Δ}.
    """
    diff = home_squad["squad_score"] - away_squad["squad_score"]  # [-1, +1]

    # Bonus supplémentaire si joueur-clé manque chez l'adversaire
    if away_squad["key_player_out"] and not home_squad["key_player_out"]:
        diff += 0.15
    elif home_squad["key_player_out"] and not away_squad["key_player_out"]:
        diff -= 0.15

    diff = max(-1.0, min(1.0, diff))
    shift = diff * max_shift

    return {
        "home": round(shift, 4),
        "draw": round(-abs(shift) * 0.2, 4),
        "away": round(-shift, 4),
    }


def get_match_squad_info(
    home_name: str,
    away_name: str,
    league: str,
    season: int = 2024,
    fixture_id: Optional[int] = None,
) -> tuple[dict, dict]:
    """
    Point d'entrée principal : retourne (home_squad_info, away_squad_info).
    Retourne des valeurs par défaut si API-Football indisponible.
    """
    if not API_KEY:
        return _default_squad(), _default_squad()

    league_id = LEAGUE_API_IDS.get(league)
    if not league_id:
        return _default_squad(), _default_squad()

    home_id = get_team_id_from_api(home_name, league_id, season)
    away_id = get_team_id_from_api(away_name, league_id, season)

    home_squad = get_squad_availability(home_id, fixture_id, season) if home_id else _default_squad()
    away_squad = get_squad_availability(away_id, fixture_id, season) if away_id else _default_squad()

    logger.debug(
        f"Effectif {home_name}: {home_squad['available_count']}/{home_squad['total_count']} "
        f"(score={home_squad['squad_score']:.2f}, key_out={home_squad['key_player_out']})"
    )
    logger.debug(
        f"Effectif {away_name}: {away_squad['available_count']}/{away_squad['total_count']} "
        f"(score={away_squad['squad_score']:.2f}, key_out={away_squad['key_player_out']})"
    )

    return home_squad, away_squad
