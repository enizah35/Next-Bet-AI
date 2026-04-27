"""
src/features/match_stats.py
Prédictions statistiques par match : buts, corners, cartons, BTTS, Over/Under.
Calcule les moyennes historiques des deux équipes et produit des estimations.
"""

import logging
from typing import Optional

from sqlalchemy import select, or_, desc, func
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import Team, MatchRaw
from src.features.team_resolver import resolve_team_map

logger = logging.getLogger(__name__)


def _team_averages(team_id: int, session: Session, last_n: int = 10) -> dict:
    """Calcule les moyennes statistiques d'une équipe sur ses N derniers matchs."""
    # Matchs à domicile — d'abord sélectionner les N derniers, puis agréger
    home_recent = (
        select(
            MatchRaw.fthg, MatchRaw.ftag,
            MatchRaw.hc, MatchRaw.ac,
            MatchRaw.hy, MatchRaw.ay,
            MatchRaw.hr, MatchRaw.hs, MatchRaw.hst,
        )
        .where(MatchRaw.home_team_id == team_id)
        .where(MatchRaw.hc.isnot(None))
        .order_by(desc(MatchRaw.date))
        .limit(last_n)
        .subquery()
    )

    stmt_home = select(
        func.avg(home_recent.c.fthg).label("avg_goals_scored"),
        func.avg(home_recent.c.ftag).label("avg_goals_conceded"),
        func.avg(home_recent.c.hc).label("avg_corners"),
        func.avg(home_recent.c.ac).label("avg_corners_conceded"),
        func.avg(home_recent.c.hy).label("avg_yellows"),
        func.avg(home_recent.c.ay).label("avg_yellows_conceded"),
        func.avg(home_recent.c.hr).label("avg_reds"),
        func.avg(home_recent.c.hs).label("avg_shots"),
        func.avg(home_recent.c.hst).label("avg_shots_on_target"),
        func.count().label("cnt"),
    )

    # Matchs à l'extérieur
    away_recent = (
        select(
            MatchRaw.ftag, MatchRaw.fthg,
            MatchRaw.ac, MatchRaw.hc,
            MatchRaw.ay, MatchRaw.hy,
            MatchRaw.ar, MatchRaw.as_shots, MatchRaw.ast,
        )
        .where(MatchRaw.away_team_id == team_id)
        .where(MatchRaw.ac.isnot(None))
        .order_by(desc(MatchRaw.date))
        .limit(last_n)
        .subquery()
    )

    stmt_away = select(
        func.avg(away_recent.c.ftag).label("avg_goals_scored"),
        func.avg(away_recent.c.fthg).label("avg_goals_conceded"),
        func.avg(away_recent.c.ac).label("avg_corners"),
        func.avg(away_recent.c.hc).label("avg_corners_conceded"),
        func.avg(away_recent.c.ay).label("avg_yellows"),
        func.avg(away_recent.c.hy).label("avg_yellows_conceded"),
        func.avg(away_recent.c.ar).label("avg_reds"),
        func.avg(away_recent.c.as_shots).label("avg_shots"),
        func.avg(away_recent.c.ast).label("avg_shots_on_target"),
        func.count().label("cnt"),
    )

    row_h = session.execute(stmt_home).first()
    row_a = session.execute(stmt_away).first()

    def safe(val, default=0.0):
        return float(val) if val is not None else default

    # Combiner home + away
    total_matches = (safe(row_h.cnt) if row_h else 0) + (safe(row_a.cnt) if row_a else 0)
    if total_matches == 0:
        return None

    def weighted_avg(h_val, a_val):
        h = safe(h_val) if row_h and row_h.cnt else 0
        a = safe(a_val) if row_a and row_a.cnt else 0
        h_cnt = safe(row_h.cnt) if row_h else 0
        a_cnt = safe(row_a.cnt) if row_a else 0
        if h_cnt + a_cnt == 0:
            return 0.0
        return (h * h_cnt + a * a_cnt) / (h_cnt + a_cnt)

    return {
        "goals_scored": weighted_avg(row_h.avg_goals_scored if row_h else 0, row_a.avg_goals_scored if row_a else 0),
        "goals_conceded": weighted_avg(row_h.avg_goals_conceded if row_h else 0, row_a.avg_goals_conceded if row_a else 0),
        "corners_for": weighted_avg(row_h.avg_corners if row_h else 0, row_a.avg_corners if row_a else 0),
        "corners_against": weighted_avg(row_h.avg_corners_conceded if row_h else 0, row_a.avg_corners_conceded if row_a else 0),
        "yellows": weighted_avg(row_h.avg_yellows if row_h else 0, row_a.avg_yellows if row_a else 0),
        "reds": weighted_avg(row_h.avg_reds if row_h else 0, row_a.avg_reds if row_a else 0),
        "shots": weighted_avg(row_h.avg_shots if row_h else 0, row_a.avg_shots if row_a else 0),
        "shots_on_target": weighted_avg(row_h.avg_shots_on_target if row_h else 0, row_a.avg_shots_on_target if row_a else 0),
        "matches": int(total_matches),
    }


def _btts_rate(team_id: int, session: Session, last_n: int = 20) -> float:
    """Calcule le taux de BTTS (Both Teams To Score) sur les N derniers matchs."""
    stmt = (
        select(MatchRaw.fthg, MatchRaw.ftag, MatchRaw.home_team_id)
        .where(or_(MatchRaw.home_team_id == team_id, MatchRaw.away_team_id == team_id))
        .order_by(desc(MatchRaw.date))
        .limit(last_n)
    )
    rows = session.execute(stmt).fetchall()
    if not rows:
        return 0.5

    btts_count = sum(1 for r in rows if r.fthg > 0 and r.ftag > 0)
    return btts_count / len(rows)


def _over_rate(team_id: int, session: Session, threshold: float = 2.5, last_n: int = 20) -> float:
    """Calcule le taux de Over X.5 goals sur les N derniers matchs."""
    stmt = (
        select(MatchRaw.fthg, MatchRaw.ftag)
        .where(or_(MatchRaw.home_team_id == team_id, MatchRaw.away_team_id == team_id))
        .order_by(desc(MatchRaw.date))
        .limit(last_n)
    )
    rows = session.execute(stmt).fetchall()
    if not rows:
        return 0.5

    over_count = sum(1 for r in rows if (r.fthg + r.ftag) > threshold)
    return over_count / len(rows)


def _last_5_form(team_id: int, session: Session) -> list[str]:
    """Retourne les 5 derniers résultats (W/D/L) du point de vue de l'équipe."""
    stmt = (
        select(MatchRaw.ftr, MatchRaw.home_team_id)
        .where(or_(MatchRaw.home_team_id == team_id, MatchRaw.away_team_id == team_id))
        .order_by(desc(MatchRaw.date))
        .limit(5)
    )
    rows = session.execute(stmt).fetchall()
    form = []
    for r in rows:
        if r.home_team_id == team_id:
            form.append("W" if r.ftr == "H" else ("D" if r.ftr == "D" else "L"))
        else:
            form.append("W" if r.ftr == "A" else ("D" if r.ftr == "D" else "L"))
    return form


def predict_match_stats(
    home_team: str,
    away_team: str,
    session: Optional[Session] = None,
    league: str = "",
) -> dict:
    """
    Prédit les statistiques d'un match basé sur les moyennes historiques.

    Returns:
        dict avec goals, corners, cards, btts, over25, form, etc.
    """
    own_session = session is None
    if own_session:
        session = get_session()

    try:
        # Récupérer les IDs
        team_map = resolve_team_map(session, [home_team, away_team], league=league)

        home_id = team_map.get(home_team)
        away_id = team_map.get(away_team)

        if not home_id or not away_id:
            return _default_stats()

        home_stats = _team_averages(home_id, session)
        away_stats = _team_averages(away_id, session)

        if not home_stats or not away_stats:
            return _default_stats()

        # Prédictions basées sur les moyennes offensives vs défensives
        pred_home_goals = (home_stats["goals_scored"] + away_stats["goals_conceded"]) / 2
        pred_away_goals = (away_stats["goals_scored"] + home_stats["goals_conceded"]) / 2
        pred_total_goals = pred_home_goals + pred_away_goals

        pred_home_corners = (home_stats["corners_for"] + away_stats["corners_against"]) / 2
        pred_away_corners = (away_stats["corners_for"] + home_stats["corners_against"]) / 2
        pred_total_corners = pred_home_corners + pred_away_corners

        pred_total_cards = (
            home_stats["yellows"] + home_stats["reds"] +
            away_stats["yellows"] + away_stats["reds"]
        )

        # BTTS : moyenne des taux des 2 équipes
        home_btts = _btts_rate(home_id, session)
        away_btts = _btts_rate(away_id, session)
        btts_pct = round((home_btts + away_btts) / 2 * 100)

        # Over 2.5
        home_over = _over_rate(home_id, session, 2.5)
        away_over = _over_rate(away_id, session, 2.5)
        over25_pct = round((home_over + away_over) / 2 * 100)

        # Over 1.5
        home_over15 = _over_rate(home_id, session, 1.5)
        away_over15 = _over_rate(away_id, session, 1.5)
        over15_pct = round((home_over15 + away_over15) / 2 * 100)

        # Forme
        home_form = _last_5_form(home_id, session)
        away_form = _last_5_form(away_id, session)

        return {
            "predicted_goals": round(pred_total_goals, 2),
            "predicted_home_goals": round(pred_home_goals, 2),
            "predicted_away_goals": round(pred_away_goals, 2),
            "predicted_corners": round(pred_total_corners, 2),
            "predicted_cards": round(pred_total_cards, 2),
            "btts_pct": btts_pct,
            "over25_pct": over25_pct,
            "over15_pct": over15_pct,
            "home_form": home_form,  # ["W", "D", "L", "W", "W"]
            "away_form": away_form,
        }

    except Exception as e:
        logger.error(f"Erreur stats {home_team} vs {away_team}: {e}")
        try:
            session.rollback()
        except Exception:
            pass
        return _default_stats()
    finally:
        if own_session:
            session.close()


def _default_stats() -> dict:
    return {
        "predicted_goals": 2.5,
        "predicted_home_goals": 1.4,
        "predicted_away_goals": 1.1,
        "predicted_corners": 10.0,
        "predicted_cards": 4.0,
        "btts_pct": 50,
        "over25_pct": 50,
        "over15_pct": 65,
        "home_form": [],
        "away_form": [],
    }
