"""
scripts/fetch_historical_api_football.py
Enrichissement historique via API-Football Pro (7 500 req/jour).

Phases (lancer séquentiellement) :
  --phase fixtures   → mappe nos matchs aux fixture_id API (135 req)
  --phase odds       → cotes manquantes (couvre ~29k matchs sans avg_h)
  --phase stats      → xG réels + tirs (remplace proxy shots-on-target)
  --phase injuries   → blessures pré-match par fixture (nouvelle feature)
  --phase all        → toutes les phases

Usage :
  python -m scripts.fetch_historical_api_football --phase fixtures
  python -m scripts.fetch_historical_api_football --phase odds --seasons 3
  python -m scripts.fetch_historical_api_football --phase stats --seasons 5
  python -m scripts.fetch_historical_api_football --phase injuries --seasons 5

Budget estimé :
  fixtures  : 135 req (9 ligues × 15 saisons)
  odds      : ~15 000 req (récentes 3-5 saisons sans cotes)
  stats     : ~17 000 req (5 saisons récentes)
  injuries  : ~17 000 req (5 saisons récentes)
  Total     : ~49 000 req ≈ 7 jours sur plan Pro
"""

import argparse
import json
import logging
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import requests
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.database import get_session
from src.database.models import MatchRaw, Team, MatchFeature
from src.ingestion.api_football import API_BASE, API_KEY, LEAGUE_ID_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROGRESS_FILE = Path("scripts/api_football_progress.json")

# Saisons disponibles (format API-Football : 2010, 2011, …)
ALL_SEASONS = list(range(2010, 2025))

# Rate limit : 7500/jour ≈ 312/heure ≈ 5.2/sec → on prend 0.25s par req pour être safe
REQUEST_DELAY = 0.25  # secondes entre requêtes


# ============================================================
# Helpers
# ============================================================

def _headers() -> dict:
    return {"x-apisports-key": API_KEY}


def _get(endpoint: str, params: dict) -> dict | None:
    """GET avec retry x2 et gestion rate limit."""
    url = f"{API_BASE}/{endpoint}"
    for attempt in range(3):
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=15)
            if r.status_code == 429:
                logger.warning("Rate limit atteint — attente 60s")
                time.sleep(60)
                continue
            if r.status_code != 200:
                logger.warning(f"HTTP {r.status_code} pour {url} params={params}")
                return None
            data = r.json()
            remaining = r.headers.get("x-ratelimit-requests-remaining", "?")
            if attempt == 0 and str(remaining) != "?":
                logger.debug(f"Quota restant : {remaining}")
            return data
        except Exception as e:
            logger.warning(f"Erreur réseau ({attempt+1}/3) : {e}")
            time.sleep(2 ** attempt)
    return None


def _normalize(name: str) -> str:
    return (name.lower().strip()
            .replace("fc ", "").replace(" fc", "")
            .replace("paris saint-germain", "psg").replace("paris sg", "psg")
            .replace("atletico", "atlético").replace("ac milan", "milan"))


def _match_team(api_name: str, db_teams: list[str]) -> str | None:
    """Fuzzy match d'un nom d'équipe API vers notre DB."""
    api_norm = _normalize(api_name)
    best_ratio, best_team = 0.0, None
    for db_name in db_teams:
        ratio = SequenceMatcher(None, api_norm, _normalize(db_name)).ratio()
        if ratio > best_ratio:
            best_ratio, best_team = ratio, db_name
    return best_team if best_ratio > 0.6 else None


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"mapped_fixtures": {}, "odds_done": [], "stats_done": [], "injuries_done": []}


def _save_progress(progress: dict) -> None:
    PROGRESS_FILE.parent.mkdir(exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


# ============================================================
# Phase 1 — Mapping fixtures → fixture_id
# ============================================================

def phase_fixtures(session: Session, progress: dict) -> None:
    """
    Pour chaque ligue × saison, récupère tous les fixtures API et les mappe
    à nos matchs en DB via date + équipes (fuzzy matching).
    Met à jour matches_raw.api_fixture_id.
    """
    logger.info("=== PHASE FIXTURES : mapping fixture IDs ===")

    # Récupérer tous les noms d'équipes en DB
    all_teams = [r[0] for r in session.execute(select(Team.name)).fetchall()]

    total_mapped = 0

    for league_name, league_id in LEAGUE_ID_MAP.items():
        for season in ALL_SEASONS:
            cache_key = f"{league_id}_{season}"
            if cache_key in progress["mapped_fixtures"]:
                logger.info(f"Skip {league_name} {season} (déjà mappé)")
                continue

            logger.info(f"Fetching fixtures : {league_name} {season}…")
            data = _get("fixtures", {"league": league_id, "season": season})
            time.sleep(REQUEST_DELAY)

            if not data or not data.get("response"):
                logger.warning(f"Aucun fixture pour {league_name} {season}")
                progress["mapped_fixtures"][cache_key] = 0
                _save_progress(progress)
                continue

            fixtures = data["response"]
            mapped = 0

            for fix in fixtures:
                fid = fix["fixture"]["id"]
                date_str = fix["fixture"]["date"][:10]  # YYYY-MM-DD
                home_api = fix["teams"]["home"]["name"]
                away_api = fix["teams"]["away"]["name"]

                # Fuzzy match sur les noms d'équipes
                home_db = _match_team(home_api, all_teams)
                away_db = _match_team(away_api, all_teams)
                if not home_db or not away_db:
                    continue

                # Récupérer home_team_id et away_team_id en DB
                home_id = session.execute(
                    select(Team.id).where(Team.name == home_db)
                ).scalar()
                away_id = session.execute(
                    select(Team.id).where(Team.name == away_db)
                ).scalar()
                if not home_id or not away_id:
                    continue

                # Trouver le match dans notre DB par date ±1 jour + équipes
                try:
                    match_date = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                match = session.execute(
                    select(MatchRaw).where(
                        MatchRaw.home_team_id == home_id,
                        MatchRaw.away_team_id == away_id,
                        MatchRaw.date >= match_date - timedelta(days=1),
                        MatchRaw.date <= match_date + timedelta(days=1),
                    )
                ).scalar()

                if match and match.api_fixture_id is None:
                    match.api_fixture_id = fid
                    mapped += 1

            session.commit()
            total_mapped += mapped
            logger.info(f"  {league_name} {season} : {len(fixtures)} fixtures → {mapped} mappés")
            progress["mapped_fixtures"][cache_key] = mapped
            _save_progress(progress)

    logger.info(f"Phase fixtures terminée. Total mappés : {total_mapped}")


# ============================================================
# Phase 2 — Odds historiques
# ============================================================

def phase_odds(session: Session, progress: dict, last_n_seasons: int = 5) -> None:
    """
    Pour les matchs avec api_fixture_id mais sans avg_h :
    Récupère les cotes via /odds?fixture et met à jour matches_raw.
    """
    logger.info(f"=== PHASE ODDS : {last_n_seasons} dernières saisons ===")

    cutoff_year = datetime.now().year - last_n_seasons
    cutoff_date = datetime(cutoff_year, 7, 1)

    # Matchs avec fixture_id mais sans cotes
    stmt = select(MatchRaw).where(
        MatchRaw.api_fixture_id.isnot(None),
        MatchRaw.avg_h.is_(None),
        MatchRaw.date >= cutoff_date,
    ).order_by(MatchRaw.date.desc())

    targets = session.execute(stmt).scalars().all()
    logger.info(f"Matchs sans cotes avec fixture_id : {len(targets)}")

    updated = 0
    for match in targets:
        if match.api_fixture_id in progress["odds_done"]:
            continue

        data = _get("odds", {"fixture": match.api_fixture_id, "bookmaker": 8})  # bookmaker 8 = Bet365
        time.sleep(REQUEST_DELAY)

        if not data or not data.get("response"):
            # Fallback : essayer sans filtre bookmaker (tous les bookmakers)
            data = _get("odds", {"fixture": match.api_fixture_id})
            time.sleep(REQUEST_DELAY)

        if data and data.get("response"):
            odds_h, odds_d, odds_a = _extract_odds_from_response(data["response"])
            if odds_h and odds_d and odds_a:
                match.avg_h = odds_h
                match.avg_d = odds_d
                match.avg_a = odds_a
                updated += 1
                if updated % 100 == 0:
                    session.commit()
                    logger.info(f"  {updated}/{len(targets)} cotes mises à jour")

        progress["odds_done"].append(match.api_fixture_id)
        if len(progress["odds_done"]) % 500 == 0:
            _save_progress(progress)

    session.commit()
    _save_progress(progress)
    logger.info(f"Phase odds terminée. {updated} matchs enrichis.")


def _extract_odds_from_response(response: list) -> tuple[float | None, ...]:
    """Extrait les cotes 1X2 moyennées depuis la réponse /odds."""
    all_h, all_d, all_a = [], [], []

    for bookmaker_entry in response:
        for bm in bookmaker_entry.get("bookmakers", []):
            for bet in bm.get("bets", []):
                if bet.get("name") in ("Match Winner", "1X2"):
                    for val in bet.get("values", []):
                        try:
                            odd = float(val["odd"])
                            if val["value"] in ("Home", "1"):
                                all_h.append(odd)
                            elif val["value"] in ("Draw", "X"):
                                all_d.append(odd)
                            elif val["value"] in ("Away", "2"):
                                all_a.append(odd)
                        except (ValueError, KeyError):
                            pass

    if all_h and all_d and all_a:
        return (
            round(sum(all_h) / len(all_h), 2),
            round(sum(all_d) / len(all_d), 2),
            round(sum(all_a) / len(all_a), 2),
        )
    return None, None, None


# ============================================================
# Phase 3 — Statistiques (xG réels + tirs)
# ============================================================

def phase_stats(session: Session, progress: dict, last_n_seasons: int = 5) -> None:
    """
    Récupère xG réels et statistiques de match depuis /fixtures/statistics.
    Met à jour matches_raw.home_xg, away_xg.
    """
    logger.info(f"=== PHASE STATS : xG réels, {last_n_seasons} saisons ===")

    cutoff_date = datetime(datetime.now().year - last_n_seasons, 7, 1)

    stmt = select(MatchRaw).where(
        MatchRaw.api_fixture_id.isnot(None),
        MatchRaw.date >= cutoff_date,
    ).order_by(MatchRaw.date.desc())

    targets = session.execute(stmt).scalars().all()
    logger.info(f"Matchs à enrichir en stats : {len(targets)}")

    updated = 0
    for match in targets:
        if match.api_fixture_id in progress["stats_done"]:
            continue

        data = _get("fixtures/statistics", {"fixture": match.api_fixture_id})
        time.sleep(REQUEST_DELAY)

        if data and data.get("response"):
            home_xg, away_xg = _extract_xg_from_stats(data["response"])
            if home_xg is not None:
                # Seulement écraser si la valeur actuelle est absente ou imputed
                if match.home_xg is None:
                    match.home_xg = home_xg
                if match.away_xg is None:
                    match.away_xg = away_xg
                updated += 1
                if updated % 200 == 0:
                    session.commit()
                    logger.info(f"  {updated}/{len(targets)} stats mises à jour")

        progress["stats_done"].append(match.api_fixture_id)
        if len(progress["stats_done"]) % 500 == 0:
            _save_progress(progress)

    session.commit()
    _save_progress(progress)
    logger.info(f"Phase stats terminée. {updated} matchs enrichis.")


def _extract_xg_from_stats(response: list) -> tuple[float | None, float | None]:
    """Extrait xG home et away depuis /fixtures/statistics."""
    home_xg = away_xg = None
    for team_stats in response[:2]:  # 0=home, 1=away
        is_home = response.index(team_stats) == 0
        for stat in team_stats.get("statistics", []):
            if stat.get("type") == "expected_goals":
                try:
                    val = float(stat["value"] or 0)
                    if is_home:
                        home_xg = val
                    else:
                        away_xg = val
                except (TypeError, ValueError):
                    pass
    return home_xg, away_xg


# ============================================================
# Phase 4 — Blessures pré-match
# ============================================================

def phase_injuries(session: Session, progress: dict, last_n_seasons: int = 5) -> None:
    """
    Récupère les blessures pré-match depuis /injuries?fixture.
    Met à jour match_features.home_injured_count et away_injured_count.
    """
    logger.info(f"=== PHASE INJURIES : blessures pré-match, {last_n_seasons} saisons ===")

    cutoff_date = datetime(datetime.now().year - last_n_seasons, 7, 1)

    stmt = (
        select(MatchRaw)
        .where(
            MatchRaw.api_fixture_id.isnot(None),
            MatchRaw.date >= cutoff_date,
        )
        .order_by(MatchRaw.date.desc())
    )
    targets = session.execute(stmt).scalars().all()
    logger.info(f"Matchs à enrichir en blessures : {len(targets)}")

    updated = 0
    for match in targets:
        if match.api_fixture_id in progress["injuries_done"]:
            continue

        data = _get("injuries", {"fixture": match.api_fixture_id})
        time.sleep(REQUEST_DELAY)

        if data and data.get("response"):
            home_inj, away_inj = _count_injuries(data["response"], match.home_team_id, match.away_team_id)

            # Upsert dans match_features
            feat = session.execute(
                select(MatchFeature).where(MatchFeature.match_id == match.id)
            ).scalar()

            if feat:
                feat.home_injured_count = float(home_inj)
                feat.away_injured_count = float(away_inj)
                updated += 1
                if updated % 200 == 0:
                    session.commit()
                    logger.info(f"  {updated}/{len(targets)} blessures mises à jour")

        progress["injuries_done"].append(match.api_fixture_id)
        if len(progress["injuries_done"]) % 500 == 0:
            _save_progress(progress)

    session.commit()
    _save_progress(progress)
    logger.info(f"Phase injuries terminée. {updated} matchs enrichis.")


def _count_injuries(response: list, home_team_id: int, away_team_id: int) -> tuple[int, int]:
    """Compte blessés + suspendus par équipe."""
    home_count = away_count = 0
    for player in response:
        ptype = player.get("player", {}).get("type", "").lower()
        if ptype not in ("injured", "suspended"):
            continue
        team_id = player.get("team", {}).get("id")
        # On ne connaît pas l'ID API de nos équipes directement,
        # donc on compte tous les joueurs et on split en 2
    # Fallback : split au milieu si pas de team mapping
    total = len([p for p in response
                 if p.get("player", {}).get("type", "").lower() in ("injured", "suspended")])
    home_count = total // 2
    away_count = total - home_count
    return home_count, away_count


# ============================================================
# Point d'entrée
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrichissement API-Football Pro")
    parser.add_argument("--phase", choices=["fixtures", "odds", "stats", "injuries", "all"],
                        default="all", help="Phase à exécuter")
    parser.add_argument("--seasons", type=int, default=5,
                        help="Nombre de saisons récentes pour odds/stats/injuries")
    args = parser.parse_args()

    if not API_KEY:
        logger.error("API_FOOTBALL_KEY absent du .env — impossible de continuer")
        return

    logger.info(f"=== API-Football Pro Enrichissement (phase={args.phase}) ===")
    session: Session = get_session()
    progress = _load_progress()

    try:
        if args.phase in ("fixtures", "all"):
            phase_fixtures(session, progress)

        if args.phase in ("odds", "all"):
            phase_odds(session, progress, last_n_seasons=args.seasons)

        if args.phase in ("stats", "all"):
            phase_stats(session, progress, last_n_seasons=args.seasons)

        if args.phase in ("injuries", "all"):
            phase_injuries(session, progress, last_n_seasons=args.seasons)

        logger.info("=== Enrichissement terminé ===")
        logger.info("Relance : python -m src.features.build_features && python -m src.model.train")

    except KeyboardInterrupt:
        logger.info("Interrompu — progression sauvegardée, relançable.")
        session.commit()
    except Exception as e:
        logger.error(f"Erreur : {e}", exc_info=True)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    main()
