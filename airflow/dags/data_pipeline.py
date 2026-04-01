from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import logging
import sys
import os

# Ajout du Root Folder au PATH pour autoriser les imports absolus des dossiers frères
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

try:
    from scrapers.fbref_scraper import get_ligue_1_standings, get_player_stats
    from scrapers.weather_api import get_stadium_weather
    from scrapers.rss_news import get_latest_football_news
    from ml_model.train import train_model
except ImportError as e:
    logging.warning(f"DAG Import Warning: {e}. Des stubs vides sont utilisés.")
    # Stubs basiques pour que le planificateur Airflow puisse au moins "parser" le fichier proprement
    def get_ligue_1_standings(): pass
    def get_player_stats(): pass
    def get_stadium_weather(*args): pass
    def get_latest_football_news(): pass
    def train_model(): pass

default_args = {
    'owner': 'bot_sport',
    'depends_on_past': False,
    'start_date': datetime(2026, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

def extract_data(**kwargs):
    """
    Tâche chargée de lancer les Scrapers.
    Dans le vrai pipeline, les DataFrames seraient stockés en DB (Postgres/S3)
    à la fin de cette fonction via SQLAlchemy ou boto3.
    """
    logging.info("Starting Data Extraction...")
    stand = get_ligue_1_standings()
    players = get_player_stats()
    news = get_latest_football_news()
    logging.info("Extraction Completed.")

def preprocess_and_train(**kwargs):
    """
    Déclenche l'entrainement basé sur les nouvelles données fraiches du jour.
    """
    logging.info("Starting AI Model Retraining...")
    train_model()
    logging.info("Model training achieved and saved.")

# Initialisation du Graphe (DAG)
with DAG(
    'bot_sport_daily_pipeline',
    default_args=default_args,
    description='Pipeline de scraping et ré-entraînement du ML',
    schedule_interval=timedelta(days=1), # S'exécute 1 fois par jour
    catchup=False,
) as dag:

    # 1. Tâche de Scraping (ETL)
    t1_extract = PythonOperator(
        task_id='extract_daily_data',
        python_callable=extract_data,
    )

    # 2. Tâche de Machine Learning
    t2_train = PythonOperator(
        task_id='retrain_ml_model',
        python_callable=preprocess_and_train,
    )

    # Ordre d'éxecution dans Airflow
    t1_extract >> t2_train
