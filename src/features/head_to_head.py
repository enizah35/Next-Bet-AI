"""
src/features/head_to_head.py
Module de calcul des confrontations directes (H2H) entre deux équipes.
Requête la base matches_raw pour les derniers face-à-face et produit des statistiques.
"""

import logging
from typing import Optional

from sqlalchemy import select, or_, and_, desc
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import Team, MatchRaw

logger = logging.getLogger(__name__)


def get_h2h_stats(
    home_team: str,
    away_team: str,
    session: Optional[Session] = None,
    max_matches: int = 10,
) -> dict:
    """
    Calcule les statistiques H2H entre deux équipes.

    Args:
        home_team: Nom de l'équipe à domicile
        away_team: Nom de l'équipe à l'extérieur
        session: Session SQLAlchemy (créée si None)
        max_matches: Nombre max de confrontations à considérer

    Returns:
        dict avec les stats H2H ou des valeurs par défaut si aucune confrontation
    """
    own_session = session is None
    if own_session:
        session = get_session()

    try:
        # Récupérer les IDs des équipes
        stmt_teams = select(Team.id, Team.name).where(Team.name.in_([home_team, away_team]))
        team_rows = session.execute(stmt_teams).fetchall()
        team_map = {r.name: r.id for r in team_rows}

        home_id = team_map.get(home_team)
        away_id = team_map.get(away_team)

        if not home_id or not away_id:
            return _default_h2h()

        # Tous les matchs entre ces deux équipes (dans les deux sens)
        stmt = (
            select(MatchRaw)
            .where(
                or_(
                    and_(MatchRaw.home_team_id == home_id, MatchRaw.away_team_id == away_id),
                    and_(MatchRaw.home_team_id == away_id, MatchRaw.away_team_id == home_id),
                )
            )
            .order_by(desc(MatchRaw.date))
            .limit(max_matches)
        )
        matches = session.execute(stmt).scalars().all()

        if not matches:
            return _default_h2h()

        # Compteurs du point de vue de home_team
        home_wins = 0
        draws = 0
        away_wins = 0
        home_goals = 0
        away_goals = 0

        for m in matches:
            if m.home_team_id == home_id:
                # Match où notre "home" jouait à domicile
                home_goals += m.fthg
                away_goals += m.ftag
                if m.ftr == "H":
                    home_wins += 1
                elif m.ftr == "D":
                    draws += 1
                else:
                    away_wins += 1
            else:
                # Match où notre "home" jouait à l'extérieur
                home_goals += m.ftag
                away_goals += m.fthg
                if m.ftr == "A":
                    home_wins += 1
                elif m.ftr == "D":
                    draws += 1
                else:
                    away_wins += 1

        total = len(matches)
        avg_goals_home = home_goals / total
        avg_goals_away = away_goals / total

        # Score de dominance [-1, 1] (positif = home domine)
        dominance = (home_wins - away_wins) / total

        return {
            "total_matches": total,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "home_win_pct": round(home_wins / total * 100, 1),
            "draw_pct": round(draws / total * 100, 1),
            "away_win_pct": round(away_wins / total * 100, 1),
            "avg_goals_home": round(avg_goals_home, 2),
            "avg_goals_away": round(avg_goals_away, 2),
            "avg_total_goals": round(avg_goals_home + avg_goals_away, 2),
            "dominance": round(dominance, 3),
        }

    except Exception as e:
        logger.error(f"Erreur H2H {home_team} vs {away_team}: {e}")
        return _default_h2h()
    finally:
        if own_session:
            session.close()


def _default_h2h() -> dict:
    """Statistiques par défaut quand aucune confrontation n'est trouvée."""
    return {
        "total_matches": 0,
        "home_wins": 0,
        "draws": 0,
        "away_wins": 0,
        "home_win_pct": 0.0,
        "draw_pct": 0.0,
        "away_win_pct": 0.0,
        "avg_goals_home": 0.0,
        "avg_goals_away": 0.0,
        "avg_total_goals": 0.0,
        "dominance": 0.0,
    }
