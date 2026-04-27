"""
src/ingestion/load_historical.py
Pipeline d'ingestion des données historiques depuis football-data.co.uk.
Télécharge les CSV, nettoie les colonnes, peuple teams puis matches_raw.
"""

import logging
import time
from io import StringIO
from typing import Optional

import numpy as np
import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.database import get_session, init_db
from src.database.models import Team, MatchRaw

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# ============================================================
# Configuration des ligues et saisons
# ============================================================
LEAGUES: list[str] = [
    "F1",   # Ligue 1
    "E0",   # Premier League
    "D1",   # Bundesliga
    "SP1",  # La Liga
    "I1",   # Serie A
    "E1",   # Championship (D2 anglaise — volume ++, style proche PL)
    "F2",   # Ligue 2
    "D2",   # 2. Bundesliga
    "SP2",  # La Liga 2
    "I2",   # Serie B
    "N1",   # Eredivisie
    "P1",   # Primeira Liga
    "T1",   # Süper Lig
    "B1",   # Belgian Pro League
    "SC0",  # Scottish Premiership
]

LEAGUE_NAMES: dict[str, str] = {
    "F1": "Ligue 1",
    "E0": "Premier League",
    "D1": "Bundesliga",
    "SP1": "La Liga",
    "I1": "Serie A",
    "E1": "Championship",
    "F2": "Ligue 2",
    "D2": "2. Bundesliga",
    "SP2": "La Liga 2",
    "I2": "Serie B",
    "N1": "Eredivisie",
    "P1": "Primeira Liga",
    "T1": "Süper Lig",
    "B1": "Belgian Pro League",
    "SC0": "Scottish Premiership",
}

# Saisons de 2010-2011 à 2025-2026
SEASONS: list[str] = [
    "1011", "1112", "1213", "1314", "1415",
    "1516", "1617", "1718", "1819", "1920",
    "2021", "2122", "2223", "2324", "2425", "2526",
]

BASE_URL: str = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"

# ============================================================
# Mapping des colonnes CSV -> colonnes du modèle matches_raw
# ============================================================
CSV_TO_MODEL_COLUMNS: dict[str, str] = {
    "Div": "div",
    "Date": "date",
    "Time": "time",
    "HomeTeam": "home_team",
    "AwayTeam": "away_team",
    "FTHG": "fthg",
    "FTAG": "ftag",
    "FTR": "ftr",
    "HTHG": "hthg",
    "HTAG": "htag",
    "HTR": "htr",
    "HS": "hs",
    "AS": "as_shots",
    "HST": "hst",
    "AST": "ast",
    "HF": "hf",
    "AF": "af",
    "HC": "hc",
    "AC": "ac",
    "HY": "hy",
    "AY": "ay",
    "HR": "hr",
    "AR": "ar",
    # Moyenne marché (format récent)
    "AvgH": "avg_h",
    "AvgD": "avg_d",
    "AvgA": "avg_a",
    "Avg>2.5": "avg_over_25",
    "Avg<2.5": "avg_under_25",
    # Clôture B365
    "B365CH": "b365_ch",
    "B365CD": "b365_cd",
    "B365CA": "b365_ca",
}

# Colonnes individuelles bookmakers — pour reconstruire avg_h quand absent
# Format ancien (<2016) : BbAvH/D/A. Format récent : AvgH/D/A.
ODDS_FALLBACK_COLUMNS: dict[str, list[str]] = {
    # Colonnes Home
    "raw_h": ["BbAvH", "B365H", "PSH", "WHH", "BWH", "IWH", "VCH", "SJH", "GBH", "BbMxH"],
    # Colonnes Draw
    "raw_d": ["BbAvD", "B365D", "PSD", "WHD", "BWD", "IWD", "VCD", "SJD", "GBD", "BbMxD"],
    # Colonnes Away
    "raw_a": ["BbAvA", "B365A", "PSA", "WHA", "BWA", "IWA", "VCA", "SJA", "GBA", "BbMxA"],
    # Over/Under 2.5
    "raw_over":  ["BbAv>2.5", "Avg>2.5"],
    "raw_under": ["BbAv<2.5", "Avg<2.5"],
    # B365 closing (pour odds_mov)
    "b365_ch": ["B365CH", "B365H"],
    "b365_cd": ["B365CD", "B365D"],
    "b365_ca": ["B365CA", "B365A"],
}

# Colonnes attendues dans le CSV source (avant renommage)
EXPECTED_CSV_COLUMNS: list[str] = list(CSV_TO_MODEL_COLUMNS.keys())


def build_urls() -> list[dict[str, str]]:
    """Génère la liste complète des URLs à télécharger."""
    urls: list[dict[str, str]] = []
    for league in LEAGUES:
        for season in SEASONS:
            url = BASE_URL.format(season=season, league=league)
            urls.append({"url": url, "league": league, "season": season})
    return urls


def download_csv(url: str) -> Optional[pd.DataFrame]:
    """Télécharge un CSV depuis une URL et retourne un DataFrame brut."""
    try:
        response: requests.Response = requests.get(url, timeout=30)
        response.raise_for_status()
        # Détection de l'encodage
        content: str = response.content.decode("utf-8", errors="replace")
        df: pd.DataFrame = pd.read_csv(StringIO(content), on_bad_lines="skip")
        return df
    except requests.RequestException as e:
        logger.warning(f"Échec du téléchargement de {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erreur de parsing pour {url}: {e}")
        return None


def _first_valid_numeric(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Retourne la première colonne non-NaN parmi cols, ou NaN si aucune."""
    result = pd.Series(np.nan, index=df.index)
    for col in cols:
        if col in df.columns:
            filled = pd.to_numeric(df[col], errors="coerce")
            mask = result.isna() & filled.notna()
            result[mask] = filled[mask]
    return result


def _avg_valid_numeric(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Moyenne des colonnes disponibles (ignore NaN)."""
    valid = [pd.to_numeric(df[c], errors="coerce") for c in cols if c in df.columns]
    if not valid:
        return pd.Series(np.nan, index=df.index)
    return pd.concat(valid, axis=1).mean(axis=1)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie le DataFrame brut.
    Récupère les cotes depuis plusieurs sources (format récent AvgH, format ancien BbAvH,
    bookmakers individuels B365/Pinnacle/WH…) pour maximiser la couverture.
    """
    # Garder toutes les colonnes — on piocher dedans avant de filtrer
    all_expected = list(EXPECTED_CSV_COLUMNS)
    for group in ODDS_FALLBACK_COLUMNS.values():
        all_expected += [c for c in group if c not in all_expected]
    df = df.reindex(columns=all_expected)

    # Renommage colonnes de base
    df = df.rename(columns=CSV_TO_MODEL_COLUMNS)

    # --- Reconstruction avg_h/d/a depuis toutes les sources disponibles ---
    # Priorité : AvgH (déjà renommé) → BbAvH → moyenne B365/Pinnacle/WH…
    for target, src_cols in [
        ("avg_h", ODDS_FALLBACK_COLUMNS["raw_h"]),
        ("avg_d", ODDS_FALLBACK_COLUMNS["raw_d"]),
        ("avg_a", ODDS_FALLBACK_COLUMNS["raw_a"]),
    ]:
        if target not in df.columns:
            df[target] = np.nan
        df[target] = pd.to_numeric(df[target], errors="coerce")
        missing = df[target].isna()
        if missing.any():
            fallback = _avg_valid_numeric(df[missing], src_cols)
            df.loc[missing, target] = fallback

    # --- Over/Under 2.5 ---
    for target, src_cols in [
        ("avg_over_25", ODDS_FALLBACK_COLUMNS["raw_over"]),
        ("avg_under_25", ODDS_FALLBACK_COLUMNS["raw_under"]),
    ]:
        if target not in df.columns:
            df[target] = np.nan
        df[target] = pd.to_numeric(df[target], errors="coerce")
        missing = df[target].isna()
        if missing.any():
            fallback = _first_valid_numeric(df[missing], src_cols)
            df.loc[missing, target] = fallback

    # --- B365 closing (odds_mov) ---
    for target, src_cols in [
        ("b365_ch", ODDS_FALLBACK_COLUMNS["b365_ch"]),
        ("b365_cd", ODDS_FALLBACK_COLUMNS["b365_cd"]),
        ("b365_ca", ODDS_FALLBACK_COLUMNS["b365_ca"]),
    ]:
        if target not in df.columns:
            df[target] = np.nan
        df[target] = pd.to_numeric(df[target], errors="coerce")
        missing = df[target].isna()
        if missing.any():
            fallback = _first_valid_numeric(df[missing], src_cols)
            df.loc[missing, target] = fallback

    # Conversion date
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date", "home_team", "away_team", "fthg", "ftag", "ftr"])

    # Types numériques
    int_columns: list[str] = ["fthg", "ftag", "hthg", "htag", "hs", "as_shots",
                               "hst", "ast", "hf", "af", "hc", "ac", "hy", "ay", "hr", "ar"]
    for col in int_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    odds_pct = df["avg_h"].notna().mean() * 100
    logger.info(f"DataFrame nettoyé : {len(df)} lignes | Couverture cotes : {odds_pct:.1f}%")
    return df


def upsert_teams(session: Session, df: pd.DataFrame, league_code: str) -> dict[str, int]:
    """
    Insère dynamiquement les équipes dans la table teams.
    Retourne un dictionnaire {nom_equipe: id}.
    """
    league_name: str = LEAGUE_NAMES.get(league_code, league_code)

    # Extraction de tous les noms d'équipes uniques
    all_team_names: set[str] = set(df["home_team"].unique()) | set(df["away_team"].unique())

    for team_name in all_team_names:
        # Upsert PostgreSQL : INSERT ... ON CONFLICT DO NOTHING
        stmt = pg_insert(Team).values(name=team_name, league=league_name)
        stmt = stmt.on_conflict_do_nothing(index_elements=["name"])
        session.execute(stmt)

    session.commit()

    # Récupération du mapping complet {nom -> id}
    result = session.execute(select(Team.name, Team.id))
    team_map: dict[str, int] = {row[0]: row[1] for row in result}

    logger.info(f"{len(all_team_names)} équipes traitées pour {league_name}")
    return team_map


def _build_match_data(row: pd.Series, team_map: dict[str, int]) -> Optional[dict]:
    """Prépare une ligne matches_raw depuis le CSV nettoyé."""
    home_name: str = row["home_team"]
    away_name: str = row["away_team"]

    home_id: Optional[int] = team_map.get(home_name)
    away_id: Optional[int] = team_map.get(away_name)
    if home_id is None or away_id is None:
        logger.warning(f"Équipe introuvable : {home_name} ou {away_name}")
        return None

    match_data: dict = {
        "div": row["div"],
        "date": row["date"],
        "time": row.get("time") if pd.notna(row.get("time")) else None,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "fthg": int(row["fthg"]),
        "ftag": int(row["ftag"]),
        "ftr": str(row["ftr"]),
        "hthg": int(row["hthg"]) if pd.notna(row.get("hthg")) else None,
        "htag": int(row["htag"]) if pd.notna(row.get("htag")) else None,
        "htr": str(row["htr"]) if pd.notna(row.get("htr")) else None,
    }

    stat_cols: list[str] = ["hs", "as_shots", "hst", "ast", "hf", "af", "hc", "ac", "hy", "ay", "hr", "ar"]
    for col in stat_cols:
        match_data[col] = int(row[col]) if pd.notna(row.get(col)) else None

    odds_cols: list[str] = ["avg_h", "avg_d", "avg_a", "avg_over_25", "avg_under_25", "b365_ch", "b365_cd", "b365_ca"]
    for col in odds_cols:
        match_data[col] = float(row[col]) if pd.notna(row.get(col)) else None

    return match_data


def insert_matches(session: Session, df: pd.DataFrame, team_map: dict[str, int], chunk_size: int = 100) -> int:
    """Insère les matchs par lots, avec retry si le pooler Supabase coupe la connexion."""
    rows: list[dict] = []
    for _, row in df.iterrows():
        match_data = _build_match_data(row, team_map)
        if match_data:
            rows.append(match_data)

    inserted_count: int = 0
    stmt = pg_insert(MatchRaw).on_conflict_do_nothing(constraint="uq_match_date_teams")

    for start in range(0, len(rows), chunk_size):
        chunk = rows[start:start + chunk_size]
        for attempt in range(3):
            try:
                session.execute(stmt, chunk)
                session.commit()
                inserted_count += len(chunk)
                break
            except OperationalError as exc:
                session.rollback()
                if attempt == 2:
                    raise
                wait_s = 2 * (attempt + 1)
                logger.warning(
                    f"Connexion DB coupée pendant l'insert batch {start}-{start + len(chunk)}. "
                    f"Retry dans {wait_s}s... ({exc.__class__.__name__})"
                )
                time.sleep(wait_s)

    logger.info(f"{inserted_count} matchs insérés/ignorés dans matches_raw")
    return inserted_count


def run_ingestion() -> bool:
    """
    Point d'entrée principal du pipeline d'ingestion.
    Télécharge toutes les saisons pour Ligue 1 et Premier League,
    nettoie les données, et les insère en base PostgreSQL.
    """
    logger.info("=" * 60)
    logger.info("DÉMARRAGE DU PIPELINE D'INGESTION")
    logger.info("=" * 60)

    # Initialisation des tables si elles n'existent pas
    init_db()

    urls: list[dict[str, str]] = build_urls()
    total_matches: int = 0

    try:
        for entry in urls:
            url: str = entry["url"]
            league: str = entry["league"]
            season: str = entry["season"]

            logger.info(f"Traitement : {LEAGUE_NAMES[league]} — Saison {season} ({url})")

            # Téléchargement
            df: Optional[pd.DataFrame] = download_csv(url)
            if df is None or df.empty:
                logger.warning(f"Aucune donnée pour {league}/{season}, passage au suivant")
                continue

            # Nettoyage
            df = clean_dataframe(df)
            if df.empty:
                logger.warning(f"DataFrame vide après nettoyage pour {league}/{season}")
                continue

            session: Session = get_session()
            try:
                # Insertion des équipes
                team_map: dict[str, int] = upsert_teams(session, df, league)

                # Insertion des matchs
                count: int = insert_matches(session, df, team_map)
                total_matches += count
            finally:
                session.close()

        logger.info("=" * 60)
        logger.info(f"INGESTION TERMINÉE — {total_matches} matchs traités au total")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale durant l'ingestion : {e}", exc_info=True)
        return False


if __name__ == "__main__":
    run_ingestion()
