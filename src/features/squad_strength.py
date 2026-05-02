"""
Live squad availability features.

The prediction pipeline uses this module to convert fixture injuries and
official lineups into a small probability adjustment. Official lineups are only
available close to kickoff, so the module also supports fixture/team injury
fallbacks.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv

from src.features.team_resolver import normalize_team_name

logger = logging.getLogger(__name__)
load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

POSITION_WEIGHTS = {
    "Goalkeeper": 5.0,
    "Defender": 4.0,
    "Midfielder": 5.5,
    "Attacker": 7.0,
}
KEY_POSITION_THRESHOLD = 6.0

LEAGUE_API_IDS = {
    "Ligue 1": 61,
    "F1": 61,
    "Premier League": 39,
    "E0": 39,
    "Bundesliga": 78,
    "D1": 78,
    "La Liga": 140,
    "SP1": 140,
    "Serie A": 135,
    "I1": 135,
    "Championship": 40,
    "E1": 40,
    "Eredivisie": 88,
    "N1": 88,
    "Primeira Liga": 94,
    "P1": 94,
    "Süper Lig": 203,
    "SÃ¼per Lig": 203,
    "SÃƒÂ¼per Lig": 203,
    "T1": 203,
    "Ligue 2": 62,
    "F2": 62,
    "2. Bundesliga": 79,
    "D2": 79,
    "La Liga 2": 141,
    "SP2": 141,
    "Serie B": 136,
    "I2": 136,
    "Belgian Pro League": 144,
    "B1": 144,
    "Scottish Premiership": 179,
    "SC0": 179,
}


def _coerce_api_season(season: int | None = None) -> int:
    now = datetime.now()
    if season is None:
        return now.year if now.month >= 7 else now.year - 1
    if season == now.year and now.month < 7:
        return season - 1
    return season


def _norm_player(name: str) -> str:
    return normalize_team_name(name or "").replace("'", " ")


def _same_player(left: str, right: str) -> bool:
    left_norm = _norm_player(left)
    right_norm = _norm_player(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    return SequenceMatcher(None, left_norm, right_norm).ratio() >= 0.88


@lru_cache(maxsize=1024)
def _api_get_cached(endpoint: str, params_items: tuple[tuple[str, str], ...]) -> dict[str, Any] | None:
    if not API_KEY:
        return None
    params = dict(params_items)
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
        if response.status_code == 429:
            logger.warning("API-Football rate limit - pause 60s")
            time.sleep(60)
            response = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        logger.debug("API-Football %s status=%s", endpoint, response.status_code)
    except Exception as exc:
        logger.debug("API-Football %s failed: %s", endpoint, exc)
    return None


def _api_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
    params_items = tuple(sorted((key, str(value)) for key, value in params.items() if value is not None))
    return _api_get_cached(endpoint, params_items)


@lru_cache(maxsize=256)
def get_team_id_from_api(team_name: str, league_id: int, season: int) -> int | None:
    data = _api_get("teams", {"name": team_name, "league": league_id, "season": _coerce_api_season(season)})
    if data and data.get("response"):
        return data["response"][0]["team"]["id"]
    return None


def _default_squad(source: str = "default") -> dict[str, Any]:
    return {
        "squad_score": 1.0,
        "available_count": 11,
        "total_count": 11,
        "key_player_out": False,
        "missing_players": [],
        "lineup_confirmed": False,
        "formation": None,
        "starters": [],
        "source": source,
    }


@lru_cache(maxsize=512)
def _fixture_lineups(fixture_id: int) -> tuple[dict[str, Any], ...]:
    data = _api_get("fixtures/lineups", {"fixture": fixture_id})
    return tuple((data or {}).get("response", []) or [])


def _parse_lineup(lineups: list[dict[str, Any]] | tuple[dict[str, Any], ...], team_api_id: int) -> dict[str, Any] | None:
    for lineup in lineups:
        if (lineup.get("team", {}) or {}).get("id") != team_api_id:
            continue
        starters = []
        for item in lineup.get("startXI", []) or []:
            player = item.get("player", {}) or {}
            if player.get("name"):
                starters.append(
                    {
                        "name": player.get("name"),
                        "position": player.get("pos"),
                        "number": player.get("number"),
                    }
                )
        return {
            "lineup_confirmed": bool(starters),
            "formation": lineup.get("formation"),
            "starters": starters,
        }
    return None


@lru_cache(maxsize=512)
def _fixture_injury_players(team_api_id: int, fixture_id: int) -> list[dict[str, Any]]:
    data = _api_get("injuries", {"fixture": fixture_id})
    players: list[dict[str, Any]] = []
    for item in (data or {}).get("response", []) or []:
        if (item.get("team", {}) or {}).get("id") != team_api_id:
            continue
        player = item.get("player", {}) or {}
        if player.get("name"):
            players.append(
                {
                    "name": player.get("name"),
                    "type": player.get("type") or "injury",
                    "reason": player.get("reason") or "",
                    "photo": player.get("photo"),
                }
            )
    return players


@lru_cache(maxsize=512)
def _team_season_injury_players(team_api_id: int, season: int) -> list[dict[str, Any]]:
    data = _api_get("injuries", {"team": team_api_id, "season": _coerce_api_season(season)})
    players: list[dict[str, Any]] = []
    for item in (data or {}).get("response", []) or []:
        player = item.get("player", {}) or {}
        name = player.get("name")
        if not name:
            continue
        injury_type = str(player.get("type") or "").lower()
        reason = str(player.get("reason") or "").lower()
        if "returned" in injury_type or "available" in reason:
            continue
        players.append(
            {
                "name": name,
                "type": player.get("type") or "injury",
                "reason": player.get("reason") or "",
                "photo": player.get("photo"),
            }
        )
    return players


@lru_cache(maxsize=512)
def _squad_weights(team_api_id: int) -> dict[str, float]:
    squad_data = _api_get("players/squads", {"team": team_api_id})
    if not squad_data or not squad_data.get("response"):
        return {}

    players = squad_data["response"][0].get("players", []) if squad_data["response"] else []
    squad: dict[str, float] = {}
    for player in players:
        name = player.get("name")
        if not name:
            continue
        position = player.get("position", "Midfielder")
        squad[name] = POSITION_WEIGHTS.get(position, 5.0)
    return squad


def get_squad_availability(
    team_api_id: int,
    fixture_id: int | None = None,
    season: int = 2024,
    fixture_injuries: list[dict[str, Any]] | None = None,
    fetch_lineups: bool = True,
) -> dict[str, Any]:
    """
    Return squad availability for one team.

    fixture_injuries can be passed by the caller to avoid a second /injuries
    request after API-Football fixture matching.
    """
    if not team_api_id:
        return _default_squad("missing_team_id")

    lineup_info: dict[str, Any] | None = None
    if fixture_id and fetch_lineups:
        lineups = _fixture_lineups(int(fixture_id))
        if lineups:
            lineup_info = _parse_lineup(lineups, team_api_id)

    if fixture_injuries is not None:
        missing_players = fixture_injuries
        source = "fixture"
    elif fixture_id:
        missing_players = _fixture_injury_players(team_api_id, fixture_id)
        source = "fixture"
    else:
        missing_players = _team_season_injury_players(team_api_id, season)
        source = "team_season"

    if not missing_players:
        fallback = _default_squad(source)
        if lineup_info:
            fallback.update(lineup_info)
            fallback["available_count"] = len(lineup_info.get("starters", [])) or fallback["available_count"]
            fallback["total_count"] = max(11, fallback["available_count"])
        return fallback

    squad = _squad_weights(team_api_id)
    if not squad:
        fallback = _default_squad(source)
        fallback["missing_players"] = missing_players
        fallback["available_count"] = max(0, fallback["total_count"] - len(missing_players))
        if lineup_info:
            fallback.update(lineup_info)
            fallback["available_count"] = len(lineup_info.get("starters", [])) or fallback["available_count"]
            fallback["total_count"] = max(11, fallback["available_count"])
        return fallback

    missing_names = [str(player.get("name") or "") for player in missing_players if player.get("name")]
    matched_missing: set[str] = set()
    missing_weight = 0.0

    for missing_name in missing_names:
        matched_name = next((name for name in squad if _same_player(name, missing_name)), None)
        if matched_name:
            matched_missing.add(matched_name)
            missing_weight += squad[matched_name]
        else:
            missing_weight += 5.0

    total_weight = sum(squad.values()) or 1.0
    avail_weight = max(0.0, total_weight - missing_weight)
    key_player_out = any(squad.get(name, 0.0) >= KEY_POSITION_THRESHOLD for name in matched_missing)

    result = {
        "squad_score": round(avail_weight / total_weight, 4),
        "available_count": max(0, len(squad) - len(matched_missing)),
        "total_count": len(squad),
        "key_player_out": key_player_out,
        "missing_players": missing_players,
        "lineup_confirmed": False,
        "formation": None,
        "starters": [],
        "source": source,
    }
    if lineup_info:
        result.update(lineup_info)
    return result


def compute_squad_adjustment(
    home_squad: dict[str, Any],
    away_squad: dict[str, Any],
    max_shift: float = 0.05,
) -> dict[str, float]:
    """
    Convert squad availability into probability deltas.
    """
    home_score = float(home_squad.get("squad_score", 1.0))
    away_score = float(away_squad.get("squad_score", 1.0))
    diff = home_score - away_score

    if away_squad.get("key_player_out") and not home_squad.get("key_player_out"):
        diff += 0.15
    elif home_squad.get("key_player_out") and not away_squad.get("key_player_out"):
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
    fixture_id: int | None = None,
    home_api_id: int | None = None,
    away_api_id: int | None = None,
    fixture_injuries: dict[str, Any] | None = None,
    fetch_lineups: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not API_KEY:
        return _default_squad("no_api_key"), _default_squad("no_api_key")

    league_id = LEAGUE_API_IDS.get(league)
    if not league_id:
        return _default_squad("unsupported_league"), _default_squad("unsupported_league")

    api_season = _coerce_api_season(season)
    home_id = home_api_id or get_team_id_from_api(home_name, league_id, api_season)
    away_id = away_api_id or get_team_id_from_api(away_name, league_id, api_season)

    home_fixture_injuries = None
    away_fixture_injuries = None
    if fixture_injuries:
        home_fixture_injuries = (fixture_injuries.get("home") or {}).get("players")
        away_fixture_injuries = (fixture_injuries.get("away") or {}).get("players")

    home_squad = (
        get_squad_availability(home_id, fixture_id, api_season, home_fixture_injuries, fetch_lineups)
        if home_id
        else _default_squad("missing_home_id")
    )
    away_squad = (
        get_squad_availability(away_id, fixture_id, api_season, away_fixture_injuries, fetch_lineups)
        if away_id
        else _default_squad("missing_away_id")
    )

    logger.debug(
        "Squad %s: %s/%s score=%.2f key_out=%s source=%s",
        home_name,
        home_squad.get("available_count"),
        home_squad.get("total_count"),
        home_squad.get("squad_score", 1.0),
        home_squad.get("key_player_out"),
        home_squad.get("source"),
    )
    logger.debug(
        "Squad %s: %s/%s score=%.2f key_out=%s source=%s",
        away_name,
        away_squad.get("available_count"),
        away_squad.get("total_count"),
        away_squad.get("squad_score", 1.0),
        away_squad.get("key_player_out"),
        away_squad.get("source"),
    )

    return home_squad, away_squad
