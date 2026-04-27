"""
scripts/migrate_db.py
Migration DB — ajoute les colonnes manquantes sans supprimer de données.
Idempotent : safe à relancer plusieurs fois.

Usage : python -m scripts.migrate_db
"""

import logging
from sqlalchemy import text
from src.database.database import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MIGRATIONS = [
    # features_json dans prediction_logs (feedback loop)
    "ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS features_json VARCHAR(8192);",
    "ALTER TABLE prediction_logs ALTER COLUMN features_json TYPE VARCHAR(8192);",

    # Lien API-Football dans matches_raw
    "ALTER TABLE matches_raw ADD COLUMN IF NOT EXISTS api_fixture_id INTEGER;",
    "CREATE INDEX IF NOT EXISTS ix_matches_raw_api_fixture_id ON matches_raw(api_fixture_id);",

    # Blessures pré-match dans match_features
    "ALTER TABLE match_features ADD COLUMN IF NOT EXISTS home_injured_count FLOAT;",
    "ALTER TABLE match_features ADD COLUMN IF NOT EXISTS away_injured_count FLOAT;",
]


def run_migrations() -> None:
    logger.info("Démarrage des migrations DB...")
    with engine.connect() as conn:
        for i, sql in enumerate(MIGRATIONS, 1):
            try:
                conn.execute(text(sql.strip()))
                conn.commit()
                logger.info(f"Migration {i}/{len(MIGRATIONS)} OK")
            except Exception as e:
                conn.rollback()
                logger.warning(f"Migration {i} ignorée (probablement déjà appliquée) : {e}")
    logger.info("Migrations terminées.")


if __name__ == "__main__":
    run_migrations()
