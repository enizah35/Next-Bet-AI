"""
Helpers to match live provider team names with the historical DB names.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import Team


TEAM_ALIASES = {
    "ac milan": "Milan",
    "aj auxerre": "Auxerre",
    "angers sco": "Angers",
    "as monaco": "Monaco",
    "as roma": "Roma",
    "athletic bilbao": "Ath Bilbao",
    "athletic": "Ath Bilbao",
    "athletic club": "Ath Bilbao",
    "alav s": "Alaves",
    "atl tico madrid": "Ath Madrid",
    "atletico madrid": "Ath Madrid",
    "brighton and hove albion": "Brighton",
    "brighton hove albion": "Brighton",
    "cadiz cf": "Cadiz",
    "deportivo alaves": "Alaves",
    "espanyol": "Espanol",
    "fc lorient": "Lorient",
    "fc metz": "Metz",
    "fc nantes": "Nantes",
    "fc porto": "Porto",
    "hellas verona": "Verona",
    "inter milan": "Inter",
    "internazionale": "Inter",
    "le havre ac": "Le Havre",
    "lille osc": "Lille",
    "losc lille": "Lille",
    "manchester city": "Man City",
    "manchester united": "Man United",
    "man united": "Man United",
    "newcastle united": "Newcastle",
    "nottingham forest": "Nott'm Forest",
    "ogc nice": "Nice",
    "olympique de marseille": "Marseille",
    "olympique lyonnais": "Lyon",
    "paris saint germain": "Paris SG",
    "paris st germain": "Paris SG",
    "psg": "Paris SG",
    "racing club de lens": "Lens",
    "rc lens": "Lens",
    "rc strasbourg": "Strasbourg",
    "real betis": "Betis",
    "real sociedad": "Sociedad",
    "stade brestois": "Brest",
    "stade brest": "Brest",
    "stade rennais": "Rennes",
    "toulouse fc": "Toulouse",
    "tottenham hotspur": "Tottenham",
}


def normalize_team_name(name: str) -> str:
    value = unicodedata.normalize("NFKD", name or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9']+", " ", value)
    value = re.sub(r"\b(fc|cf|ac|sc|afc|calcio|club)\b", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _row_maps(rows) -> tuple[dict[str, tuple[int, str]], dict[str, tuple[int, str]]]:
    by_exact = {row.name: (row.id, row.name) for row in rows}
    by_norm: dict[str, tuple[int, str]] = {}
    for row in rows:
        by_norm.setdefault(normalize_team_name(row.name), (row.id, row.name))
    return by_exact, by_norm


def _resolve_one(name: str, rows, by_exact, by_norm) -> tuple[int, str] | None:
    if name in by_exact:
        return by_exact[name]

    norm = normalize_team_name(name)
    if norm in by_norm:
        return by_norm[norm]

    alias = TEAM_ALIASES.get(norm)
    if alias:
        if alias in by_exact:
            return by_exact[alias]
        alias_norm = normalize_team_name(alias)
        if alias_norm in by_norm:
            return by_norm[alias_norm]

    best: tuple[float, tuple[int, str] | None] = (0.0, None)
    for row in rows:
        candidate_norm = normalize_team_name(row.name)
        score = SequenceMatcher(None, norm, candidate_norm).ratio()
        if score > best[0]:
            best = (score, (row.id, row.name))

    if best[0] >= 0.88:
        return best[1]
    return None


def resolve_team_map(session: Session, names: list[str], league: str = "") -> dict[str, int]:
    """
    Return a map from the live names requested by the caller to DB team IDs.
    Exact match wins, then aliases, then a conservative fuzzy match.
    """
    stmt = select(Team.id, Team.name)
    if league:
        stmt = stmt.where(Team.league == league)
    rows = session.execute(stmt).fetchall()
    if not rows and league:
        rows = session.execute(select(Team.id, Team.name)).fetchall()

    by_exact, by_norm = _row_maps(rows)
    result: dict[str, int] = {}
    for name in names:
        resolved = _resolve_one(name, rows, by_exact, by_norm)
        if resolved:
            result[name] = resolved[0]
    return result
