"""
src/database/database.py
Moteur SQLAlchemy 2.0+ et gestion de session pour PostgreSQL.
"""

import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Chargement des variables d'environnement
load_dotenv()

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# URL de connexion PostgreSQL depuis le fichier .env
DATABASE_URL: str = os.getenv("DB_URL", "postgresql://user:pass@localhost:5432/nextbet")

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
    Base.metadata.create_all(bind=engine)
    logger.info("Tables créées avec succès.")


if __name__ == "__main__":
    init_db()
