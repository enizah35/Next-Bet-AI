"""
dags/daily_pipeline.py
DAG Airflow pour l'orchestration quotidienne du pipeline Next-Bet-AI.
Exécution chaque jour à 07:00 UTC.
Tâches : Ingestion des données -> Feature Engineering
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# ============================================================
# Configuration du DAG
# ============================================================
default_args: dict = {
    "owner": "next-bet-ai",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}


def task_ingestion() -> None:
    """Tâche 1 : Exécuter le pipeline d'ingestion des données historiques."""
    from src.ingestion.load_historical import run_ingestion

    success: bool = run_ingestion()
    if not success:
        raise RuntimeError("Le pipeline d'ingestion a échoué.")


def task_feature_engineering() -> None:
    """Tâche 2 : Exécuter le calcul des features pour le Deep Learning."""
    from src.features.build_features import run_feature_engineering

    success: bool = run_feature_engineering()
    if not success:
        raise RuntimeError("Le feature engineering a échoué.")


# ============================================================
# Définition du DAG
# ============================================================
with DAG(
    dag_id="next_bet_ai_daily_pipeline",
    default_args=default_args,
    description="Pipeline quotidien Next-Bet-AI : Ingestion + Feature Engineering",
    schedule_interval="0 7 * * *",  # Chaque jour à 07:00 UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["next-bet-ai", "deep-learning", "football"],
) as dag:

    # Tâche 1 : Ingestion
    ingest_task = PythonOperator(
        task_id="run_ingestion",
        python_callable=task_ingestion,
    )

    # Tâche 2 : Feature Engineering
    features_task = PythonOperator(
        task_id="run_feature_engineering",
        python_callable=task_feature_engineering,
    )

    # Dépendance : Ingestion AVANT Feature Engineering
    ingest_task >> features_task
