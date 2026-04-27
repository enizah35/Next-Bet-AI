"""
src/features/feature_extractor.py
Extraction des features pour l'inférence en temps réel (matchs à venir).
Lit les dernières lignes MatchFeature depuis la DB pour chaque équipe.
"""

import logging
import math
import os
from typing import Optional
from sqlalchemy import select, desc, or_
from sqlalchemy.orm import Session

from src.database.models import MatchRaw, MatchFeature
from src.features.team_resolver import resolve_team_map

logger = logging.getLogger(__name__)
LIVE_OPPONENT_WEIGHTED_FORM = os.getenv("LIVE_OPPONENT_WEIGHTED_FORM", "true").lower() == "true"

# Taux historiques par ligue (H%, D%, A%) — calculés sur les données 2010-2025
LEAGUE_BASE_RATES: dict[str, tuple[float, float, float]] = {
    "Ligue 1":        (0.444, 0.285, 0.271),
    "Premier League": (0.464, 0.264, 0.272),
    "Bundesliga":     (0.446, 0.267, 0.287),
    "La Liga":        (0.461, 0.269, 0.270),
    "Serie A":        (0.447, 0.276, 0.277),
    "Championship":   (0.430, 0.275, 0.295),
    "Eredivisie":     (0.488, 0.238, 0.274),
    "Primeira Liga":  (0.467, 0.264, 0.269),
    "Süper Lig":      (0.459, 0.270, 0.271),
    "Ligue 2":        (0.435, 0.280, 0.285),
    "2. Bundesliga":  (0.438, 0.272, 0.290),
    "La Liga 2":      (0.440, 0.275, 0.285),
    "Serie B":        (0.432, 0.282, 0.286),
    "Belgian Pro League": (0.450, 0.265, 0.285),
    "Scottish Premiership": (0.455, 0.260, 0.285),
}
_DEFAULT_RATES = (0.455, 0.270, 0.275)  # fallback si ligue inconnue

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
    "Belgian Pro League": "B1",
    "Scottish Premiership": "SC0",
}

# Valeurs par défaut si la donnée est absente (correspondent aux moyennes approximatives)
FEATURE_DEFAULTS = {
    "implied_home": 0.40,
    "implied_draw": 0.27,
    "implied_away": 0.33,
    "home_elo": 1500.0,
    "away_elo": 1500.0,
    "elo_diff": 0.0,
    "home_pts_last_5": 1.5,
    "home_goals_scored_last_5": 1.3,
    "home_goals_conceded_last_5": 1.1,
    "away_pts_last_5": 1.3,
    "away_goals_scored_last_5": 1.1,
    "away_goals_conceded_last_5": 1.3,
    "home_pts_last_5_at_home": 1.8,
    "away_pts_last_5_away": 1.0,
    "home_sot_last_5": 4.5,
    "away_sot_last_5": 4.0,
    "home_sot_conceded_last_5": 4.0,
    "away_sot_conceded_last_5": 4.5,
    "home_xg_last_5": 1.3,
    "away_xg_last_5": 1.1,
    "home_days_rest": 7.0,
    "away_days_rest": 7.0,
    "home_unbeaten_streak": 2.0,
    "away_unbeaten_streak": 2.0,
    "home_momentum": 1.0,
    "away_momentum": 1.0,
    "h2h_dominance": 0.0,
    "h2h_avg_goals": 2.5,
    "form_pts_diff": 0.0,
    "goal_diff_home": 0.2,
    "goal_diff_away": -0.2,
    "implied_over25": 0.5,
    "odds_mov_home": 0.0,
    "odds_mov_draw": 0.0,
    "home_injured_count": 0.0,
    "away_injured_count": 0.0,
    "injury_diff": 0.0,
    "league_home_rate": 0.455,
    "league_draw_rate": 0.270,
    "league_away_rate": 0.275,
    "market_home_away_gap": 0.07,
    "market_favorite_prob": 0.40,
    "market_draw_gap": -0.13,
    "market_entropy": 1.09,
    "form_goal_diff": 0.4,
    "xg_diff": 0.2,
    "sot_diff": 0.5,
    "sot_conceded_diff": -0.5,
    "rest_diff": 0.0,
    "momentum_diff": 0.0,
    "unbeaten_diff": 0.0,
    "home_attack_vs_away_defense": 0.0,
    "away_attack_vs_home_defense": 0.0,
    "attack_balance": 0.0,
}

# Colonnes MatchFeature à lire côté domicile
HOME_FEATURE_COLS = [
    "home_pts_last_5", "home_goals_scored_last_5", "home_goals_conceded_last_5",
    "home_elo", "home_pts_last_5_at_home", "home_sot_last_5", "home_sot_conceded_last_5",
    "home_xg_last_5", "home_days_rest", "home_unbeaten_streak", "home_momentum",
    "h2h_dominance", "h2h_avg_goals",
]

# Colonnes MatchFeature à lire côté extérieur
AWAY_FEATURE_COLS = [
    "away_pts_last_5", "away_goals_scored_last_5", "away_goals_conceded_last_5",
    "away_elo", "away_pts_last_5_away", "away_sot_last_5", "away_sot_conceded_last_5",
    "away_xg_last_5", "away_days_rest", "away_unbeaten_streak", "away_momentum",
]


def _league_to_div(league: str) -> str | None:
    if not league:
        return None
    upper = league.upper()
    if upper in set(LEAGUE_NAME_TO_DIV.values()):
        return upper
    return LEAGUE_NAME_TO_DIV.get(league)


def _get_latest_feature_row(
    team_id: int,
    as_home: bool,
    session: Session,
    league_code: str | None = None,
) -> Optional[MatchFeature]:
    """Retourne la dernière ligne MatchFeature où l'équipe jouait à domicile (ou extérieur)."""
    if as_home:
        stmt = (
            select(MatchFeature)
            .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
            .where(MatchRaw.home_team_id == team_id)
            .order_by(desc(MatchRaw.date))
            .limit(1)
        )
    else:
        stmt = (
            select(MatchFeature)
            .join(MatchRaw, MatchFeature.match_id == MatchRaw.id)
            .where(MatchRaw.away_team_id == team_id)
        )

    if league_code:
        stmt = stmt.where(MatchRaw.div == league_code)

    stmt = stmt.order_by(desc(MatchRaw.date)).limit(1)
    row = session.execute(stmt).scalar()
    if row is None and league_code:
        return _get_latest_feature_row(team_id, as_home=as_home, session=session, league_code=None)
    return row


def _points_for_match(match: MatchRaw, team_id: int) -> int:
    is_home = match.home_team_id == team_id
    if match.fthg == match.ftag:
        return 1
    if is_home:
        return 3 if match.fthg > match.ftag else 0
    return 3 if match.ftag > match.fthg else 0


def _weighted_recent_form(team_id: int, session: Session, limit: int = 5) -> dict[str, float] | None:
    """
    Forme récente pondérée par la force de l'adversaire.
    Les points obtenus contre une équipe forte pèsent plus que les points contre une équipe faible.
    """
    stmt = (
        select(MatchRaw, MatchFeature)
        .outerjoin(MatchFeature, MatchFeature.match_id == MatchRaw.id)
        .where(or_(MatchRaw.home_team_id == team_id, MatchRaw.away_team_id == team_id))
        .order_by(desc(MatchRaw.date))
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    if not rows:
        return None

    weighted_points: list[float] = []
    goals_scored: list[float] = []
    goals_conceded: list[float] = []

    for match, feature in rows:
        is_home = match.home_team_id == team_id
        opponent_elo = 1500.0
        if feature:
            raw_elo = feature.away_elo if is_home else feature.home_elo
            opponent_elo = float(raw_elo if raw_elo is not None else 1500.0)
        weight = max(0.75, min(1.25, opponent_elo / 1500.0))
        weighted_points.append(_points_for_match(match, team_id) * weight)
        goals_scored.append(float(match.fthg if is_home else match.ftag))
        goals_conceded.append(float(match.ftag if is_home else match.fthg))

    return {
        "pts_last_5": sum(weighted_points) / len(weighted_points),
        "goals_scored_last_5": sum(goals_scored) / len(goals_scored),
        "goals_conceded_last_5": sum(goals_conceded) / len(goals_conceded),
    }


def _blend(current: float, improved: float, strength: float = 0.35) -> float:
    return (current * (1.0 - strength)) + (improved * strength)


def extract_match_features(
    home_name: str,
    away_name: str,
    session: Session,
    league: str = "",
    implied_home: Optional[float] = None,
    implied_draw: Optional[float] = None,
    implied_away: Optional[float] = None,
    avg_h: Optional[float] = None,
    avg_d: Optional[float] = None,
    avg_a: Optional[float] = None,
    odds_mov_home: Optional[float] = None,
    odds_mov_draw: Optional[float] = None,
) -> dict:
    """
    Extrait les features pour un match à venir.
    Cherche les équipes par nom exact dans la DB, puis lit leurs dernières stats.

    Les probabilités implicites peuvent être passées directement ou calculées
    depuis les cotes brutes (avg_h/d/a).
    Retourne toujours un dict complet avec defaults pour les valeurs manquantes.
    """
    features = dict(FEATURE_DEFAULTS)
    league_code = _league_to_div(league)
    home_id = None
    away_id = None

    # Taux historiques de la ligue
    h_rate, d_rate, a_rate = LEAGUE_BASE_RATES.get(league, _DEFAULT_RATES)
    features["league_home_rate"] = h_rate
    features["league_draw_rate"] = d_rate
    features["league_away_rate"] = a_rate

    # Requêtes DB — silencieusement ignorées si la DB est indisponible
    try:
        team_map = resolve_team_map(session, [home_name, away_name], league=league)

        home_id = team_map.get(home_name)
        away_id = team_map.get(away_name)

        if home_id:
            row = _get_latest_feature_row(home_id, as_home=True, session=session, league_code=league_code)
            if row:
                for col in HOME_FEATURE_COLS:
                    val = getattr(row, col, None)
                    if val is not None:
                        features[col] = float(val)

        if away_id:
            row = _get_latest_feature_row(away_id, as_home=False, session=session, league_code=league_code)
            if row:
                for col in AWAY_FEATURE_COLS:
                    val = getattr(row, col, None)
                    if val is not None:
                        features[col] = float(val)

        if LIVE_OPPONENT_WEIGHTED_FORM:
            if home_id:
                weighted_home = _weighted_recent_form(home_id, session=session)
                if weighted_home:
                    features["home_pts_last_5"] = _blend(features["home_pts_last_5"], weighted_home["pts_last_5"])
                    features["home_goals_scored_last_5"] = _blend(
                        features["home_goals_scored_last_5"], weighted_home["goals_scored_last_5"], strength=0.25
                    )
                    features["home_goals_conceded_last_5"] = _blend(
                        features["home_goals_conceded_last_5"], weighted_home["goals_conceded_last_5"], strength=0.25
                    )
            if away_id:
                weighted_away = _weighted_recent_form(away_id, session=session)
                if weighted_away:
                    features["away_pts_last_5"] = _blend(features["away_pts_last_5"], weighted_away["pts_last_5"])
                    features["away_goals_scored_last_5"] = _blend(
                        features["away_goals_scored_last_5"], weighted_away["goals_scored_last_5"], strength=0.25
                    )
                    features["away_goals_conceded_last_5"] = _blend(
                        features["away_goals_conceded_last_5"], weighted_away["goals_conceded_last_5"], strength=0.25
                    )
    except Exception as e:
        logger.warning(f"DB indisponible pour {home_name} vs {away_name}, utilisation des defaults : {e}")

    # Elo diff
    features["elo_diff"] = features["home_elo"] - features["away_elo"]

    # Probabilités implicites (depuis cotes brutes si disponibles)
    if avg_h and avg_d and avg_a:
        margin = (1.0 / avg_h) + (1.0 / avg_d) + (1.0 / avg_a)
        features["implied_home"] = (1.0 / avg_h) / margin
        features["implied_draw"] = (1.0 / avg_d) / margin
        features["implied_away"] = (1.0 / avg_a) / margin
    elif implied_home is not None and implied_draw is not None and implied_away is not None:
        features["implied_home"] = implied_home
        features["implied_draw"] = implied_draw
        features["implied_away"] = implied_away
    else:
        home_adv_elo = 60.0
        draw_rate = features["league_draw_rate"]
        p_home_raw = 1.0 / (1.0 + 10.0 ** ((features["away_elo"] - features["home_elo"] - home_adv_elo) / 400.0))
        features["implied_home"] = p_home_raw * (1.0 - draw_rate)
        features["implied_away"] = (1.0 - p_home_raw) * (1.0 - draw_rate)
        features["implied_draw"] = draw_rate

    if odds_mov_home is not None:
        features["odds_mov_home"] = odds_mov_home
    if odds_mov_draw is not None:
        features["odds_mov_draw"] = odds_mov_draw

    # Interactions engineered
    features["form_pts_diff"] = features["home_pts_last_5"] - features["away_pts_last_5"]
    features["goal_diff_home"] = features["home_goals_scored_last_5"] - features["home_goals_conceded_last_5"]
    features["goal_diff_away"] = features["away_goals_scored_last_5"] - features["away_goals_conceded_last_5"]
    market_probs = [
        max(1e-6, min(1.0, features["implied_home"])),
        max(1e-6, min(1.0, features["implied_draw"])),
        max(1e-6, min(1.0, features["implied_away"])),
    ]
    features["market_home_away_gap"] = features["implied_home"] - features["implied_away"]
    features["market_favorite_prob"] = max(market_probs)
    features["market_draw_gap"] = features["implied_draw"] - max(features["implied_home"], features["implied_away"])
    features["market_entropy"] = -sum(p * math.log(p) for p in market_probs)
    features["form_goal_diff"] = features["goal_diff_home"] - features["goal_diff_away"]
    features["xg_diff"] = features["home_xg_last_5"] - features["away_xg_last_5"]
    features["sot_diff"] = features["home_sot_last_5"] - features["away_sot_last_5"]
    features["sot_conceded_diff"] = features["home_sot_conceded_last_5"] - features["away_sot_conceded_last_5"]
    features["rest_diff"] = features["home_days_rest"] - features["away_days_rest"]
    features["momentum_diff"] = features["home_momentum"] - features["away_momentum"]
    features["unbeaten_diff"] = features["home_unbeaten_streak"] - features["away_unbeaten_streak"]
    features["home_attack_vs_away_defense"] = features["home_goals_scored_last_5"] - features["away_goals_conceded_last_5"]
    features["away_attack_vs_home_defense"] = features["away_goals_scored_last_5"] - features["home_goals_conceded_last_5"]
    features["attack_balance"] = features["home_attack_vs_away_defense"] - features["away_attack_vs_home_defense"]

    return features
