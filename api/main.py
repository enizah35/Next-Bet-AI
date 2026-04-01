import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import random
import logging

try:
    from scrapers.fbref_scraper import get_upcoming_matches_7_days
    from scrapers.weather_api import get_stadium_weather_bulk
    from scrapers.rss_news import fetch_all_football_news, get_team_injuries_from_pool
    from ml_model.predict import predict_match
except ImportError as e:
    logging.error(f"Cannot import ML scripts: {e}")
    # Fallback dev mode si imports corrompus
    def get_upcoming_matches_7_days(): return []
    def predict_match(*args): return None

app = FastAPI(title="Next-Bet-AI", description="API pour prédictions d'IA (Phase 3: Deep Learning, PostgreSQL & Value Bets)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "API V2: Bot Sport AI Live Data Pipeline"}

@app.get("/predictions/today")
def get_today_predictions():
    # 1. On récupère la totalité des vrais matchs des 7 prochains jours (Ligue 1 + Premier League)
    upcoming = get_upcoming_matches_7_days()
    
    if not upcoming:
        upcoming = [
            {"homeTeam": "Paris SG", "awayTeam": "Marseille", "date": "10/05/26 à 20:45", "competition": "Ligue 1", "form_home": 0.8, "form_away": 0.6},
            {"homeTeam": "Arsenal", "awayTeam": "Man City", "date": "12/05/26 à 17:30", "competition": "Premier League",  "form_home": 0.9, "form_away": 0.5}
        ]
        
    # Optimisation Flash Phase 3 : Fetch tous les flux une seule fois par requete globale (Ultra Rapide)
    news_pool = fetch_all_football_news()
    
    # On isole les équipes locales pour la météo
    home_teams = list(set([m['homeTeam'] for m in upcoming]))
    weather_map = get_stadium_weather_bulk(home_teams)
    
    results = []
    
    # 2. Pour chaqu'un de ces matchs réels, on va assembler les facteurs IA en temps continu :
    for idx, match in enumerate(upcoming):
        
        # A) La Forme Mathématique (Calculée en scraper depuis le Standings FBref V W D L W)
        form_a = match.get('form_home', 0.5)
        form_b = match.get('form_away', 0.5)
        
        # B) Les Blessures ou Crises issues de l'Actu (RSS L'Equipe/BBC scannant les noms des clubs réels)
        inj_a = get_team_injuries_from_pool(match['homeTeam'], news_pool)
        inj_b = get_team_injuries_from_pool(match['awayTeam'], news_pool)
        
        # C) La Météo locale en se basant sur un array de longitude/latitude du stade Récepteur
        weather = weather_map.get(match['homeTeam'], 1)
        
        # 3. L'Inférence Pure: On demande à la FORET ALEATOIRE ce qu'elle pense de ces facteurs asyncheones réels
        ai_probs = predict_match(form_a, form_b, inj_a, inj_b, weather)
        
        if ai_probs is None:
            # Fallback en cas où rf_model.joblib disparait de la ROM : calcul proxy formel
            advantage = form_a - form_b
            base_p1 = min(85.0, max(15.0, 45.0 + (advantage * 40)))
            ai_probs = {
                "prob_1": base_p1,
                "prob_N": 25.0,
                "prob_2": 100.0 - base_p1 - 25.0
            }

        injuries_badge = []
        if inj_a > 0:
            injuries_badge.append(f"{inj_a} Alerte(s) Presse ({match['homeTeam']})")
        if inj_b > 0:
            injuries_badge.append(f"{inj_b} Alerte(s) Presse ({match['awayTeam']})")

        # 4. Détection de Value Bet
        # Seuil par défaut : +10% d'écart positif entre l'IA et le Bookmaker
        value_bet = {"active": False, "edge": 0, "target": None}
        book_probs = match.get("bookmaker_probs", {})
        
        # On check les 3 issues (1, N, 2)
        mapping = {"1": "prob_1", "N": "prob_N", "2": "prob_2"}
        for key, ai_key in mapping.items():
            b_p = book_probs.get(key)
            if b_p is not None:
                b_p_scaled = b_p * 100
                edge = ai_probs[ai_key] - b_p_scaled
                if edge > 10: # +10% de value
                    if not value_bet["active"] or edge > value_bet["edge"]:
                        value_bet = {
                            "active": True,
                            "edge": float(round(edge, 1)),
                            "target": key,
                            "bookmaker_prob": float(round(b_p_scaled, 1))
                        }
        
        # 5. Pari Conseillé (Heuristique Decisionnelle avec Double Chance)
        recommendation = "Analyses en cours..."
        p1, pn, p2 = ai_probs["prob_1"], ai_probs["prob_N"], ai_probs["prob_2"]
        
        if value_bet["active"]:
            target_map = {"1": match['homeTeam'], "N": "Match Nul", "2": match['awayTeam']}
            recommendation = f"Parier sur : {target_map.get(value_bet['target'])} (Value Bet)"
        elif p1 > 75:
            recommendation = f"Victoire de {match['homeTeam']} (Confiance Haute)"
        elif p2 > 75:
            recommendation = f"Victoire de {match['awayTeam']} (Confiance Haute)"
        elif (p1 + pn) > 82:
            recommendation = f"{match['homeTeam']} ou Nul (Double Chance - Sécurisé)"
        elif (p2 + pn) > 82:
            recommendation = f"{match['awayTeam']} ou Nul (Double Chance - Sécurisé)"
        elif p1 > 55:
            recommendation = f"Victoire de {match['homeTeam']} (Modéré)"
        elif p2 > 55:
            recommendation = f"Victoire de {match['awayTeam']} (Modéré)"
        else:
            recommendation = "Prudence : Match incertain"

        results.append({
            "id": idx + 1,
            "homeTeam": match['homeTeam'],
            "awayTeam": match['awayTeam'],
            "date": match['date'], 
            "competition": match['competition'],
            "injuries": injuries_badge,
            "valueBet": value_bet,
            "recommendation": recommendation,
            "probs": {
                "p1": float(round(ai_probs.get("prob_1"), 1)),
                "pn": float(round(ai_probs.get("prob_N"), 1)),
                "p2": float(round(ai_probs.get("prob_2"), 1))
            },
            "details": {
                "formHome": float(form_a),
                "formAway": float(form_b),
                "weatherCode": int(weather),
                "injuriesCountHome": int(inj_a),
                "injuriesCountAway": int(inj_b)
            }
        })
        
    return results
