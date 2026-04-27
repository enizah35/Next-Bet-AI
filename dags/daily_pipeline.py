"""
dags/daily_pipeline.py
DAG Airflow — Pipeline Next-Bet-AI.

Schedules :
  • Quotidien 07:00 UTC  : ingestion + feature engineering
  • Hebdomadaire lundi 05:00 UTC : feedback retrain du méta-learner
  • Mensuel 1er du mois 04:00 UTC : re-entraînement complet
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args: dict = {
    "owner": "next-bet-ai",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

# ============================================================
# Tâches
# ============================================================

def task_ingestion() -> None:
    from src.ingestion.load_historical import run_ingestion
    if not run_ingestion():
        raise RuntimeError("Ingestion échouée.")


def task_feature_engineering() -> None:
    from src.features.build_features import run_feature_engineering
    if not run_feature_engineering():
        raise RuntimeError("Feature engineering échoué.")


def task_feedback_retrain() -> None:
    """Re-entraîne uniquement le méta-learner avec les prédictions vérifiées de la semaine."""
    from scripts.retrain_with_feedback import run_feedback_retrain
    # 30 samples minimum pour déclencher
    run_feedback_retrain(min_samples=30)


def task_full_retrain() -> None:
    """Re-entraînement complet : NN + XGBoost + LightGBM + méta-learner."""
    from src.model.train import run_training
    if not run_training():
        raise RuntimeError("Re-entraînement complet échoué.")


def task_clear_injury_cache() -> None:
    """Vide le cache LRU des blessures (api-sports.io) en début de journée."""
    from src.ingestion.api_football import clear_injury_cache
    clear_injury_cache()


# ============================================================
# DAG 1 : Pipeline quotidien — ingestion + features + cache
# ============================================================
with DAG(
    dag_id="next_bet_ai_daily_pipeline",
    default_args=default_args,
    description="Ingestion quotidienne + feature engineering + cache blessures",
    schedule_interval="0 7 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["next-bet-ai", "daily"],
) as dag_daily:

    ingest_task = PythonOperator(task_id="run_ingestion", python_callable=task_ingestion)
    features_task = PythonOperator(task_id="run_feature_engineering", python_callable=task_feature_engineering)
    clear_cache_task = PythonOperator(task_id="clear_injury_cache", python_callable=task_clear_injury_cache)

    ingest_task >> features_task
    clear_cache_task  # indépendant


# ============================================================
# DAG 2 : Feedback retrain hebdomadaire (lundi 05:00 UTC)
# ============================================================
with DAG(
    dag_id="next_bet_ai_feedback_retrain",
    default_args=default_args,
    description="Re-entraînement du méta-learner avec les prédictions vérifiées (hebdo)",
    schedule_interval="0 5 * * 1",  # chaque lundi à 05:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["next-bet-ai", "ml", "feedback"],
) as dag_feedback:

    PythonOperator(task_id="feedback_retrain", python_callable=task_feedback_retrain)


# ============================================================
# DAG 3 : Re-entraînement complet mensuel (1er du mois, 04:00 UTC)
# ============================================================
with DAG(
    dag_id="next_bet_ai_full_retrain",
    default_args={**default_args, "retries": 1},
    description="Re-entraînement complet NN+XGB+LGB+méta (mensuel)",
    schedule_interval="0 4 1 * *",  # 1er de chaque mois à 04:00
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["next-bet-ai", "ml", "full-retrain"],
) as dag_monthly:

    ingest_monthly = PythonOperator(task_id="run_ingestion_full", python_callable=task_ingestion)
    features_monthly = PythonOperator(task_id="run_features_full", python_callable=task_feature_engineering)
    retrain_task = PythonOperator(task_id="full_retrain", python_callable=task_full_retrain)

    ingest_monthly >> features_monthly >> retrain_task
