"""
src/ingestion/load_understat.py
Script asynchrone pour l'ingestion des métriques avancées (xG, xPTS) depuis Understat.
Cible : Ligue 1 et Premier League. (Saisons 2014 à 2023).
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import asyncio
import logging
from datetime import datetime, timedelta

import aiohttp
from understat import Understat
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import MatchRaw, Team
from src.utils.mappings import get_fd_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

async def fetch_and_update(session: aiohttp.ClientSession, db_session: Session, league_understat: str, league_fd: str, year: int):
    logger.info(f"Début extraction pour {league_understat} - Saison {year}")
    understat = Understat(session)
    
    try:
        results = await understat.get_league_results(league_understat, year)
    except Exception as e:
        logger.error(f"Erreur téléchargement {league_understat} {year} : {e}")
        return

    logger.info(f"Trouvé {len(results)} matchs sur Understat pour {league_understat} {year}")

    # Pré-fetch du dictionnaire de teams pour cette ligue (pour accélérer)
    stmt_teams = select(Team.id, Team.name).where(Team.league == league_fd)
    teams = {r.name: r.id for r in db_session.execute(stmt_teams).fetchall()}

    updated_count = 0
    not_found_count = 0

    for match in results:
        try:
            # Understat data structure:
            # match['h']['title'] = home team name
            # match['a']['title'] = away team name
            # match['xG']['h'] = home xG
            # match['xG']['a'] = away xG
            # match['datetime'] = '2014-08-16 11:45:00'
            home_u = match["h"]["title"]
            away_u = match["a"]["title"]
            date_str = match["datetime"]
            
            hxG = float(match.get("xG", {}).get("h", 0))
            axG = float(match.get("xG", {}).get("a", 0))
            hxPts = float(match.get("xpts", {}).get("h", 0) if "xpts" in match else 0)
            axPts = float(match.get("xpts", {}).get("a", 0) if "xpts" in match else 0)

            # Translation
            home_fd = get_fd_name(home_u)
            home_id = teams.get(home_fd)

            if not home_id:
                not_found_count += 1
                logger.debug(f"Equipe {home_fd} introuvable en DB.")
                continue

            # Approche Date : on cherche dans une fenêtre de ± 24h
            match_dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            start_dt = match_dt - timedelta(days=1)
            end_dt = match_dt + timedelta(days=1)

            stmt_match = select(MatchRaw.id).where(
                (MatchRaw.home_team_id == home_id) &
                (MatchRaw.date >= start_dt) &
                (MatchRaw.date <= end_dt)
            ).limit(1)

            row = db_session.execute(stmt_match).scalar()

            if row:
                stmt_upd = (
                    update(MatchRaw)
                    .where(MatchRaw.id == row)
                    .values(
                        home_xg=hxG,
                        away_xg=axG,
                        home_xpts=hxPts if hxPts else None,
                        away_xpts=axPts if axPts else None
                    )
                )
                db_session.execute(stmt_upd)
                updated_count += 1
            else:
                not_found_count += 1

        except Exception as e:
            logger.warning(f"Failed parsing match: {e}")

    db_session.commit()
    logger.info(f"Saison {year} - {league_understat} : {updated_count} matchs updatés, {not_found_count} introuvables.")

async def main():
    logger.info("Démarrage du processus Load Understat")
    
    # Understat ids: 'ligue_1', 'epl'
    # Notre DB: 'F1', 'E0'
    tasks_cfg = [
        ("epl", "E0"),
        ("ligue_1", "F1")
    ]
    
    db_session = get_session()

    async with aiohttp.ClientSession() as http_session:
        # Loop des années demandées 2014 à 2023
        for league_u, league_fd in tasks_cfg:
            for year in range(2014, 2024):
                await fetch_and_update(http_session, db_session, league_u, league_fd, year)
                # Small sleep to prevent rate limiting
                await asyncio.sleep(1)

    db_session.close()
    logger.info("Pipeline Understat terminé.")

if __name__ == "__main__":
    # Correction pour asyncio sous Windows 
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
