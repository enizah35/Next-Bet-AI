"""
src/ingestion/load_historical.py
Pipeline d'ingestion des données historiques depuis football-data.co.uk.
Télécharge les CSV, nettoie les colonnes, peuple teams puis matches_raw.
"""

import logging
from io import StringIO
from typing import Optional

import pandas as pd
import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.database.database import get_session, init_db
from src.database.models import Team, MatchRaw

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# ============================================================
# Configuration des ligues et saisons
# ============================================================
LEAGUES: list[str] = ["F1", "E0"]  # F1 = Ligue 1, E0 = Premier League

LEAGUE_NAMES: dict[str, str] = {
    "F1": "Ligue 1",
    "E0": "Premier League",
}

# Saisons de 2010-2011 à 2023-2024
SEASONS: list[str] = [
    "1011", "1112", "1213", "1314", "1415",
    "1516", "1617", "1718", "1819", "1920",
    "2021", "2122", "2223", "2324",
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
    "AvgH": "avg_h",
    "AvgD": "avg_d",
    "AvgA": "avg_a",
    "Avg>2.5": "avg_over_25",
    "Avg<2.5": "avg_under_25",
    "B365CH": "b365_ch",
    "B365CD": "b365_cd",
    "B365CA": "b365_ca",
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


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Nettoie le DataFrame brut :
    1. Filtre uniquement les colonnes pertinentes pour matches_raw
    2. Utilise reindex pour créer les colonnes manquantes (NaN) — évite KeyError
    3. Convertit les dates proprement
    """
    # Étape 1 : Reindex pour garantir la présence de toutes les colonnes
    # Les colonnes absentes seront remplies avec NaN (pas de KeyError)
    df = df.reindex(columns=EXPECTED_CSV_COLUMNS)

    # Étape 2 : Renommage vers les noms du modèle SQLAlchemy
    df = df.rename(columns=CSV_TO_MODEL_COLUMNS)

    # Étape 3 : Conversion de la date (format DD/MM/YYYY ou DD/MM/YY)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    # Étape 4 : Suppression des lignes sans date ou sans résultat
    df = df.dropna(subset=["date", "home_team", "away_team", "fthg", "ftag", "ftr"])

    # Étape 5 : Types numériques
    int_columns: list[str] = ["fthg", "ftag", "hthg", "htag", "hs", "as_shots",
                               "hst", "ast", "hf", "af", "hc", "ac", "hy", "ay", "hr", "ar"]
    for col in int_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    float_columns: list[str] = ["avg_h", "avg_d", "avg_a", "avg_over_25", "avg_under_25",
                                 "b365_ch", "b365_cd", "b365_ca"]
    for col in float_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    logger.info(f"DataFrame nettoyé : {len(df)} lignes retenues")
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


def insert_matches(session: Session, df: pd.DataFrame, team_map: dict[str, int]) -> int:
    """Insère les matchs dans matches_raw avec gestion des doublons."""
    inserted_count: int = 0

    for _, row in df.iterrows():
        home_name: str = row["home_team"]
        away_name: str = row["away_team"]

        home_id: Optional[int] = team_map.get(home_name)
        away_id: Optional[int] = team_map.get(away_name)

        if home_id is None or away_id is None:
            logger.warning(f"Équipe introuvable : {home_name} ou {away_name}")
            continue

        # Préparation des valeurs pour l'insertion
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

        # Statistiques (nullable)
        stat_cols: list[str] = ["hs", "as_shots", "hst", "ast", "hf", "af",
                                 "hc", "ac", "hy", "ay", "hr", "ar"]
        for col in stat_cols:
            match_data[col] = int(row[col]) if pd.notna(row.get(col)) else None

        # Cotes (nullable)
        odds_cols: list[str] = ["avg_h", "avg_d", "avg_a", "avg_over_25", "avg_under_25",
                                 "b365_ch", "b365_cd", "b365_ca"]
        for col in odds_cols:
            match_data[col] = float(row[col]) if pd.notna(row.get(col)) else None

        # Upsert : insérer ou ignorer si doublon (date + home + away)
        stmt = pg_insert(MatchRaw).values(**match_data)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_match_date_teams")
        session.execute(stmt)
        inserted_count += 1

    session.commit()
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

    session: Session = get_session()

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

            # Insertion des équipes
            team_map: dict[str, int] = upsert_teams(session, df, league)

            # Insertion des matchs
            count: int = insert_matches(session, df, team_map)
            total_matches += count

        logger.info("=" * 60)
        logger.info(f"INGESTION TERMINÉE — {total_matches} matchs traités au total")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"Erreur fatale durant l'ingestion : {e}", exc_info=True)
        session.rollback()
        return False

    finally:
        session.close()


if __name__ == "__main__":
    run_ingestion()
