import xgboost as xgb
import pandas as pd
import logging
import os

logging.basicConfig(level=logging.INFO)

def predict_match(team_a_form: float, team_b_form: float, team_a_injuries: int, team_b_injuries: int, weather_code: int):
    """
    Retourne les probabilités (1, N, 2) pour un match donné en interrogeant XGBoost.
    """
    model_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(model_dir, 'xgboost_model.json')
    
    if not os.path.exists(model_path):
        logging.error("XGBoost Model file not found. Run train.py first.")
        return None
    
    # Chargement natif XGBoost (rapide)
    clf = xgb.XGBClassifier()
    clf.load_model(model_path)
    
    # Création du DataFrame
    features = pd.DataFrame([{
        'team_a_form': team_a_form,
        'team_b_form': team_b_form,
        'team_a_injuries': team_a_injuries,
        'team_b_injuries': team_b_injuries,
        'weather_code': weather_code
    }])
    
    probas = clf.predict_proba(features)[0] 
    
    # Pour l'heuristique, classes = [0, 1, 2] ordonnées par defaut sur XGBClassifier binned.
    # On garantit que : Class 0 = Nul, Class 1 = Aagne, Class 2 = Bgagne
    result = {
        "prob_N": float(round(probas[0] * 100, 1)),
        "prob_1": float(round(probas[1] * 100, 1)),
        "prob_2": float(round(probas[2] * 100, 1))
    }
            
    logging.info(f"XGB Prediction generated: P1={result['prob_1']}% | PN={result['prob_N']}% | P2={result['prob_2']}%")
    return result

if __name__ == "__main__":
    res = predict_match(0.8, 0.6, 1, 0, 2)
    print(f"Probabilités du match test: {res}")
