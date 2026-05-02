"""
API-Football live helpers.

This module is used only at inference time. It links provider matches to
API-Football fixtures, then exposes fixture injuries and team ids so the live
pipeline can use real availability data instead of generic defaults.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

import requests
from dotenv import load_dotenv

from src.features.team_resolver import normalize_team_name

logger = logging.getLogger(__name__)
load_dotenv()

API_BASE = "https://v3.football.api-sports.io"
API_KEY = os.getenv("API_FOOTBALL_KEY", "")


TEAM_ID_MAP: dict[str, int] = {
    # Premier League
    "Arsenal": 42,
    "Aston Villa": 66,
    "Bournemouth": 35,
    "Brentford": 55,
    "Brighton": 51,
    "Chelsea": 49,
    "Crystal Palace": 52,
    "Everton": 45,
    "Fulham": 36,
    "Ipswich": 57,
    "Leicester": 46,
    "Liverpool": 40,
    "Man City": 50,
    "Manchester City": 50,
    "Man United": 33,
    "Manchester United": 33,
    "Newcastle": 34,
    "Newcastle United": 34,
    "Nott'm Forest": 65,
    "Nottingham Forest": 65,
    "Southampton": 41,
    "Tottenham": 47,
    "West Ham": 48,
    "Wolves": 39,
    # Ligue 1
    "Paris SG": 85,
    "Paris Saint Germain": 85,
    "Marseille": 81,
    "Lyon": 80,
    "Monaco": 91,
    "Lille": 79,
    "Nice": 84,
    "Rennes": 94,
    "Lens": 116,
    "Montpellier": 82,
    "Strasbourg": 95,
    "Toulouse": 96,
    "Nantes": 83,
    "Brest": 106,
    "Le Havre": 111,
    "Reims": 93,
    "St Etienne": 1063,
    "Saint-Etienne": 1063,
    "Angers": 77,
    "Metz": 112,
    # Bundesliga
    "Bayern Munich": 157,
    "Borussia Dortmund": 165,
    "Dortmund": 165,
    "RB Leipzig": 173,
    "Bayer Leverkusen": 168,
    "Leverkusen": 168,
    "Frankfurt": 169,
    "Stuttgart": 172,
    "Hoffenheim": 167,
    "Freiburg": 160,
    "Augsburg": 170,
    "Wolfsburg": 161,
    # La Liga
    "Real Madrid": 541,
    "Barcelona": 529,
    "Atletico Madrid": 530,
    "Ath Madrid": 530,
    "Sevilla": 536,
    "Real Sociedad": 548,
    "Sociedad": 548,
    "Real Betis": 543,
    "Betis": 543,
    "Villarreal": 533,
    "Valencia": 532,
    "Athletic Club": 531,
    "Ath Bilbao": 531,
    # Serie A
    "Juventus": 496,
    "Inter": 505,
    "AC Milan": 489,
    "Milan": 489,
    "Napoli": 492,
    "Roma": 497,
    "Lazio": 487,
    "Atalanta": 499,
    "Fiorentina": 502,
}


LEAGUE_ID_MAP: dict[str, int] = {
    "Premier League": 39,
    "E0": 39,
    "Championship": 40,
    "E1": 40,
    "Ligue 1": 61,
    "F1": 61,
    "Ligue 2": 62,
    "F2": 62,
    "Bundesliga": 78,
    "D1": 78,
    "2. Bundesliga": 79,
    "D2": 79,
    "La Liga": 140,
    "SP1": 140,
    "La Liga 2": 141,
    "SP2": 141,
    "Serie A": 135,
    "I1": 135,
    "Serie B": 136,
    "I2": 136,
    "Eredivisie": 88,
    "N1": 88,
    "Primeira Liga": 94,
    "P1": 94,
    "Süper Lig": 203,
    "SÃ¼per Lig": 203,
    "SÃƒÂ¼per Lig": 203,
    "Super Lig": 203,
    "T1": 203,
    "Belgian Pro League": 144,
    "B1": 144,
    "Scottish Premiership": 179,
    "SC0": 179,
}


TEAM_NAME_ALIASES: dict[str, str] = {
    "ath bilbao": "athletic club",
    "ath madrid": "atletico madrid",
    "betis": "real betis",
    "dortmund": "borussia dortmund",
    "frankfurt": "eintracht frankfurt",
    "inter": "inter milan",
    "leverkusen": "bayer leverkusen",
    "man city": "manchester city",
    "man united": "manchester united",
    "milan": "ac milan",
    "nott m forest": "nottingham forest",
    "nottingham forest": "nottingham forest",
    "paris sg": "paris saint germain",
    "psg": "paris saint germain",
    "saint etienne": "saint etienne",
    "st etienne": "saint etienne",
    "sociedad": "real sociedad",
    "spurs": "tottenham",
}


def _headers() -> dict[str, str]:
    return {"x-apisports-key": API_KEY}


def _norm(value: str) -> str:
    normalized = normalize_team_name(value or "").replace("'", " ")
    normalized = " ".join(normalized.split())
    return TEAM_NAME_ALIASES.get(normalized, normalized)


def _team_similarity(left: str, right: str) -> float:
    left_norm = _norm(left)
    right_norm = _norm(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm == right_norm:
        return 1.0
    if len(left_norm) >= 5 and len(right_norm) >= 5 and (left_norm in right_norm or right_norm in left_norm):
        return 0.92
    return SequenceMatcher(None, left_norm, right_norm).ratio()


def _team_matches(left: str, right: str) -> bool:
    return _team_similarity(left, right) >= 0.76


def _coerce_api_season(season: int | None = None) -> int:
    """
    API-Football uses the season start year. In April 2026, the live season is
    2025, not 2026.
    """
    now = datetime.now()
    if season is None:
        return now.year if now.month >= 7 else now.year - 1
    if season == now.year and now.month < 7:
        return season - 1
    return season


def get_current_api_season() -> int:
    return _coerce_api_season(None)


def get_league_id(league: str) -> int | None:
    if league in LEAGUE_ID_MAP:
        return LEAGUE_ID_MAP[league]
    league_norm = _norm(league)
    for label, league_id in LEAGUE_ID_MAP.items():
        if _norm(label) == league_norm:
            return league_id
    return None


def parse_match_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(value[:10], "%Y-%m-%d")
            except ValueError:
                return None
    return None


@lru_cache(maxsize=512)
def _api_get_cached(endpoint: str, params_items: tuple[tuple[str, str], ...]) -> dict[str, Any] | None:
    if not API_KEY:
        return None

    params = dict(params_items)
    try:
        response = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=_headers(),
            params=params,
            timeout=10,
        )
        if response.status_code != 200:
            logger.debug("API-Football %s status=%s body=%s", endpoint, response.status_code, response.text[:160])
            return None
        return response.json()
    except Exception as exc:
        logger.debug("API-Football %s failed: %s", endpoint, exc)
        return None


def _api_get(endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
    clean_params = tuple(sorted((key, str(value)) for key, value in params.items() if value is not None))
    return _api_get_cached(endpoint, clean_params)


@lru_cache(maxsize=128)
def get_fixtures_for_window(
    league: str,
    start_date: str,
    end_date: str,
    season: int | None = None,
) -> tuple[dict[str, Any], ...]:
    league_id = get_league_id(league)
    if not league_id:
        return ()

    data = _api_get(
        "fixtures",
        {
            "league": league_id,
            "season": _coerce_api_season(season),
            "from": start_date,
            "to": end_date,
        },
    )
    if not data:
        return ()
    return tuple(data.get("response") or ())


def _fixture_payload(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_info = fixture.get("fixture", {}) or {}
    teams = fixture.get("teams", {}) or {}
    home = teams.get("home", {}) or {}
    away = teams.get("away", {}) or {}
    status = fixture_info.get("status", {}) or {}
    return {
        "fixture_id": fixture_info.get("id"),
        "home_api_id": home.get("id"),
        "away_api_id": away.get("id"),
        "home_api_name": home.get("name"),
        "away_api_name": away.get("name"),
        "kickoff": fixture_info.get("date"),
        "status": status.get("short") or status.get("long"),
        "source": "api_football",
    }


def _best_fixture_match(
    fixtures: tuple[dict[str, Any], ...],
    home_team: str,
    away_team: str,
    match_dt: datetime | None,
) -> dict[str, Any] | None:
    best_score = 0.0
    best_fixture: dict[str, Any] | None = None

    for fixture in fixtures:
        payload = _fixture_payload(fixture)
        home_api = str(payload.get("home_api_name") or "")
        away_api = str(payload.get("away_api_name") or "")
        home_score = _team_similarity(home_team, home_api)
        away_score = _team_similarity(away_team, away_api)
        if home_score < 0.76 or away_score < 0.76:
            continue

        date_score = 0.0
        fixture_dt = parse_match_datetime(payload.get("kickoff"))
        if fixture_dt and match_dt:
            day_gap = abs((fixture_dt.date() - match_dt.date()).days)
            if day_gap > 1:
                continue
            date_score = 0.2 if day_gap == 0 else 0.05

        score = home_score + away_score + date_score
        if score > best_score:
            best_score = score
            best_fixture = payload

    return best_fixture


@lru_cache(maxsize=512)
def _resolve_fixture_cached(
    home_team: str,
    away_team: str,
    league: str,
    match_date_key: str,
    season: int,
) -> dict[str, Any]:
    match_dt = parse_match_datetime(match_date_key) if match_date_key else None
    center = match_dt or datetime.now()
    start = (center - timedelta(days=1)).date().isoformat()
    end = (center + timedelta(days=1)).date().isoformat()
    fixtures = get_fixtures_for_window(league, start, end, season)
    fixture = _best_fixture_match(fixtures, home_team, away_team, match_dt)
    return fixture or {}


def resolve_fixture_for_match(
    home_team: str,
    away_team: str,
    league: str,
    match_date: Any = None,
    season: int | None = None,
) -> dict[str, Any]:
    match_dt = parse_match_datetime(match_date)
    match_date_key = match_dt.date().isoformat() if match_dt else ""
    return _resolve_fixture_cached(home_team, away_team, league, match_date_key, _coerce_api_season(season))


def attach_fixture_ids(matches: list[dict[str, Any]], league: str, season: int | None = None) -> list[dict[str, Any]]:
    if not matches or not API_KEY or not get_league_id(league):
        return matches

    dates = [parse_match_datetime(match.get("dateStr") or match.get("date")) for match in matches]
    valid_dates = [dt for dt in dates if dt]
    if valid_dates:
        start = (min(valid_dates) - timedelta(days=1)).date().isoformat()
        end = (max(valid_dates) + timedelta(days=1)).date().isoformat()
    else:
        today = datetime.now().date()
        start = today.isoformat()
        end = (today + timedelta(days=8)).isoformat()

    fixtures = get_fixtures_for_window(league, start, end, season)
    if not fixtures:
        return matches

    attached: list[dict[str, Any]] = []
    for match in matches:
        match_dt = parse_match_datetime(match.get("dateStr") or match.get("date"))
        fixture = _best_fixture_match(fixtures, match.get("homeTeam", ""), match.get("awayTeam", ""), match_dt)
        if fixture:
            match = {
                **match,
                "fixtureId": fixture.get("fixture_id"),
                "apiHomeTeamId": fixture.get("home_api_id"),
                "apiAwayTeamId": fixture.get("away_api_id"),
                "apiFootballFixture": fixture,
            }
        attached.append(match)
    return attached


def _player_from_injury(item: dict[str, Any]) -> dict[str, Any] | None:
    player = item.get("player", {}) or {}
    name = player.get("name")
    if not name:
        return None
    return {
        "name": name,
        "type": player.get("type") or "injury",
        "reason": player.get("reason") or "",
        "photo": player.get("photo"),
    }


@lru_cache(maxsize=512)
def get_fixture_injuries(
    fixture_id: int,
    home_api_id: int | None = None,
    away_api_id: int | None = None,
) -> dict[str, Any]:
    if not API_KEY or not fixture_id:
        return {
            "source": "none",
            "home": {"count": 0, "players": []},
            "away": {"count": 0, "players": []},
        }

    data = _api_get("injuries", {"fixture": fixture_id})
    home_players: list[dict[str, Any]] = []
    away_players: list[dict[str, Any]] = []

    for item in (data or {}).get("response", []) or []:
        parsed = _player_from_injury(item)
        if not parsed:
            continue
        team_id = (item.get("team", {}) or {}).get("id")
        if home_api_id and team_id == home_api_id:
            home_players.append(parsed)
        elif away_api_id and team_id == away_api_id:
            away_players.append(parsed)

    return {
        "source": "fixture",
        "home": {"count": len(home_players), "players": home_players},
        "away": {"count": len(away_players), "players": away_players},
    }


def _is_active_injury(item: dict[str, Any]) -> bool:
    player = item.get("player", {}) or {}
    if not player.get("name"):
        return False
    injury_type = str(player.get("type") or "").lower()
    reason = str(player.get("reason") or "").lower()
    inactive_markers = ("returned", "available")
    return not any(marker in injury_type or marker in reason for marker in inactive_markers)


@lru_cache(maxsize=512)
def get_team_injuries(team_id: int, league_id: int, season: int) -> int:
    """
    Count current team injuries/suspensions. Kept as a fallback when a fixture id
    cannot be resolved.
    """
    if not API_KEY or not team_id or not league_id:
        return 0

    data = _api_get(
        "injuries",
        {"team": team_id, "league": league_id, "season": _coerce_api_season(season)},
    )
    if not data:
        return 0
    return sum(1 for item in data.get("response", []) or [] if _is_active_injury(item))


def _lookup_team_id(team_name: str) -> int | None:
    if team_name in TEAM_ID_MAP:
        return TEAM_ID_MAP[team_name]
    team_norm = _norm(team_name)
    for label, team_id in TEAM_ID_MAP.items():
        if _norm(label) == team_norm:
            return team_id
    return None


def get_injuries_for_match(
    home_team: str,
    away_team: str,
    league: str,
    season: int | None = None,
    fixture_id: int | None = None,
    home_api_id: int | None = None,
    away_api_id: int | None = None,
    return_details: bool = False,
) -> tuple[int, int] | tuple[int, int, dict[str, Any]]:
    """
    Return injury counts for a match.

    Preference order:
    1. /injuries?fixture=... when the live fixture was resolved.
    2. /injuries?team=...&league=...&season=... fallback.
    """
    if fixture_id:
        details = get_fixture_injuries(int(fixture_id), home_api_id, away_api_id)
        home_count = int(details["home"]["count"])
        away_count = int(details["away"]["count"])
        if return_details:
            return home_count, away_count, details
        return home_count, away_count

    league_id = get_league_id(league)
    home_id = home_api_id or _lookup_team_id(home_team)
    away_id = away_api_id or _lookup_team_id(away_team)
    api_season = _coerce_api_season(season)

    home_inj = get_team_injuries(int(home_id), int(league_id), api_season) if home_id and league_id else 0
    away_inj = get_team_injuries(int(away_id), int(league_id), api_season) if away_id and league_id else 0
    details = {
        "source": "team_season" if league_id else "none",
        "home": {"count": home_inj, "players": []},
        "away": {"count": away_inj, "players": []},
    }

    if return_details:
        return home_inj, away_inj, details
    return home_inj, away_inj


def injury_adjustment(home_injuries: int, away_injuries: int) -> dict[str, float]:
    """
    Probability adjustment based on injury differential. Positive home_adj means
    a small advantage to the home team.
    """
    delta = (away_injuries - home_injuries) * 0.015
    delta = max(-0.10, min(0.10, delta))
    return {"home_adj": round(delta, 4), "away_adj": round(-delta, 4)}


def clear_injury_cache() -> None:
    get_team_injuries.cache_clear()
    get_fixture_injuries.cache_clear()
    get_fixtures_for_window.cache_clear()
    _resolve_fixture_cached.cache_clear()
    _api_get_cached.cache_clear()
