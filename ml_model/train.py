import pandas as pd
import sqlite3
import random
import numpy as np
import os
import logging
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from database.db_setup import DB_PATH, init_db

logging.basicConfig(level=logging.INFO)

def seed_historic_data(num_records=5000):
    """
    Simule la présence d'une base de données historique de 5000 matchs
    pour le XGBoost d'après l'heuristique de rentabilité.
    """
    logging.info(f"Seeding {num_records} matches into SQL Database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Vide la table pour clean run
    cursor.execute("DELETE FROM matches_history")
    
    np.random.seed(42)
    records = []
    for _ in range(num_records):
        form_a = round(random.uniform(0.1, 0.9), 2)
        form_b = round(random.uniform(0.1, 0.9), 2)
        inj_a = random.randint(0, 3)
        inj_b = random.randint(0, 3)
        weather = random.randint(1, 3)
        
        strength_a = form_a - (inj_a * 0.08)
        strength_b = form_b - (inj_b * 0.08)
        diff = strength_a - strength_b
        
        if weather == 3:
            diff *= 0.6 
            
        if diff > 0.08:
            res = 1 # Equipe locale gagne
        elif diff < -0.08:
            res = 2 # Equipe adverse gagne
        else:
            res = 0 # Match Nul
            
        records.append((form_a, form_b, inj_a, inj_b, weather, res))
        
    cursor.executemany('''
        INSERT INTO matches_history (team_a_form, team_b_form, team_a_injuries, team_b_injuries, weather_code, result)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', records)
    conn.commit()
    conn.close()

def train_xgboost_model():
    """Forme le XGBoost ultra optimisé depuis les données historiques SQL."""
    logging.info("Starting XGBoost training pipeline...")
    
    init_db()
    seed_historic_data(5000)
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM matches_history", conn)
    conn.close()
    
    X = df.drop(columns=['id', 'result'])
    y = df['result']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
    
    clf = XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.05,
        use_label_encoder=False,
        eval_metric='mlogloss',
        objective='multi:softprob'
    )
    clf.fit(X_train, y_train)
    
    preds = clf.predict(X_test)
    logging.info(f"XGBoost Accuracy on Test Set: {accuracy_score(y_test, preds):.2f}")
    
    model_path = os.path.join(os.path.dirname(__file__), 'xgboost_model.json')
    clf.save_model(model_path)
    logging.info(f"XGBoost Model saved down to {model_path}")

if __name__ == "__main__":
    train_xgboost_model()
