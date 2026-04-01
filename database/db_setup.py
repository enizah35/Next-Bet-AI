import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot_sport.db")

def init_db():
    logging.info(f"Initialisation de la base de donnees SQLite a {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Historique de ML pour la Phase 3 XGBoost
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_a_form REAL,
            team_b_form REAL,
            team_a_injuries INTEGER,
            team_b_injuries INTEGER,
            weather_code INTEGER,
            result INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    logging.info("Base de donnees prete et table matches_history configuree.")

if __name__ == "__main__":
    init_db()
