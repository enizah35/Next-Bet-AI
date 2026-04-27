"""
src/database/database.py
Moteur SQLAlchemy 2.0+ et gestion de session pour PostgreSQL.
"""

import os
import logging
import socket
from urllib.parse import urlparse
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session

# Chargement des variables d'environnement
load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# URL de connexion PostgreSQL.
# DB_URL_POOLER est prioritaire: l'URL directe Supabase peut nécessiter IPv6.
DB_URL_VAR = os.getenv("DB_URL_POOLER") or os.getenv("DB_URL")
if not DB_URL_VAR:
    logger.warning("ALERTE : DB_URL/DB_URL_POOLER non détectée. Utilisation du fallback localhost.")
else:
    source = "DB_URL_POOLER" if os.getenv("DB_URL_POOLER") else "DB_URL"
    logger.info(f"{source} détectée (Longueur: {len(DB_URL_VAR)} caractères)")
    parsed_db_url = urlparse(DB_URL_VAR)
    if (
        source == "DB_URL_POOLER"
        and parsed_db_url.hostname
        and parsed_db_url.hostname.startswith("db.")
        and parsed_db_url.port == 5432
    ):
        logger.warning(
            "DB_URL_POOLER pointe encore vers l'hôte direct Supabase db.<project>.supabase.co. "
            "Copie l'URL Connection Pooling Supabase: host en *.pooler.supabase.com ou port 6543."
        )

DATABASE_URL: str = DB_URL_VAR or "postgresql://user:pass@localhost:5432/nextbet"

# Création de l'engine SQLAlchemy 2.0 avec pool de connexions
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Factory de sessions
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    """Crée et retourne une nouvelle session SQLAlchemy."""
    return SessionLocal()


def init_db() -> None:
    """Initialise la base de données en créant toutes les tables définies dans models.py."""
    from src.database.models import Base

    logger.info("Création des tables dans la base de données PostgreSQL...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Tables créées avec succès.")
        migrate_db()
    except OperationalError as e:
        original = str(getattr(e, "orig", e))
        if "could not translate host name" in original or isinstance(getattr(e, "orig", None), socket.gaierror):
            logger.error(
                "Connexion DB impossible: le hostname PostgreSQL ne se résout pas. "
                "Avec Supabase, DB_URL_POOLER ne doit pas contenir db.<project>.supabase.co. "
                "Il faut l'URL Connection Pooling avec un host *.pooler.supabase.com."
            )
        raise


def migrate_db() -> None:
    """Ajoute les nouvelles colonnes aux tables existantes (idempotent, IF NOT EXISTS)."""
    from sqlalchemy import text

    migrations = [
        # Feedback loop : vecteur de features au moment de la prédiction
        "ALTER TABLE prediction_logs ADD COLUMN IF NOT EXISTS features_json VARCHAR(4096)",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                logger.info(f"Migration OK : {sql[:60]}...")
            except Exception as e:
                logger.warning(f"Migration ignorée ({e}): {sql[:60]}...")
        conn.commit()
    logger.info("Migrations terminées.")


if __name__ == "__main__":
    init_db()
