"""
src/api/main.py
Backend FastAPI pour Next-Bet-AI.
Routes : /health (GET), /predict (POST)
Intègre le modèle PyTorch MatchPredictor avec 15 features avancées.
"""

import logging
import os
import stripe
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text, select, desc
from sqlalchemy.orm import Session

from src.model.predict import predictor_service
from src.database.database import get_session
from src.database.models import Profile

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# ============================================================
# Lifespan : chargement du modèle au démarrage
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("--- Démarrage de l'API Next-Bet-AI (v2.2) ---")
    success: bool = predictor_service.load()
    if success:
        logger.info("Modèle PyTorch (15 features) chargé avec succès")
    else:
        logger.warning("Modèle PyTorch non disponible — /predict utilisera le fallback")
    
    # Vérification des clés Stripe
    if not stripe.api_key:
        logger.error("DANGER : STRIPE_SECRET_KEY non configurée !")
    else:
        logger.debug("Stripe API key détectée")

    logger.info("--- API Prête à recevoir des requêtes ---")
    yield
    # Shutdown
    logger.info("Fermeture de l'application...")

# ============================================================
# Application FastAPI
# ============================================================
app: FastAPI = FastAPI(
    title="Next-Bet-AI",
    description="API de prédiction de matchs de football par Deep Learning (Ligue 1 & Premier League)",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://next-bet-ai.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Configuration Stripe
# ============================================================
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
stripe_webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

# Mapping des Price IDs (configurés dans le Dashboard Stripe)
PRICE_MAP = {
    "ligue1": {
        "monthly": os.getenv("STRIPE_PRICE_LIGUE1_MONTHLY"),
        "yearly": os.getenv("STRIPE_PRICE_LIGUE1_YEARLY"),
    },
    "pl": {
        "monthly": os.getenv("STRIPE_PRICE_PL_MONTHLY"),
        "yearly": os.getenv("STRIPE_PRICE_PL_YEARLY"),
    },
    "ultimate": {
        "monthly": os.getenv("STRIPE_PRICE_ULTIMATE_MONTHLY"),
        "yearly": os.getenv("STRIPE_PRICE_ULTIMATE_YEARLY"),
    }
}

# ============================================================
# Schémas Pydantic
# ============================================================
class PredictRequest(BaseModel):
    """Schéma de la requête de prédiction avec 15 features."""
    home_team: str = Field(..., description="Nom de l'équipe à domicile")
    away_team: str = Field(..., description="Nom de l'équipe à l'extérieur")

    # Forme générale (6)
    home_pts_last_5: Optional[float] = Field(None, description="Moyenne points domicile sur 5 matchs")
    away_pts_last_5: Optional[float] = Field(None, description="Moyenne points extérieur sur 5 matchs")
    home_goals_scored_last_5: Optional[float] = Field(None, description="Buts marqués domicile (moy. 5 matchs)")
    home_goals_conceded_last_5: Optional[float] = Field(None, description="Buts encaissés domicile (moy. 5 matchs)")
    away_goals_scored_last_5: Optional[float] = Field(None, description="Buts marqués extérieur (moy. 5 matchs)")
    away_goals_conceded_last_5: Optional[float] = Field(None, description="Buts encaissés extérieur (moy. 5 matchs)")

    # Elo (3)
    home_elo: Optional[float] = Field(None, description="Rating Elo de l'équipe domicile")
    away_elo: Optional[float] = Field(None, description="Rating Elo de l'équipe extérieur")
    elo_diff: Optional[float] = Field(None, description="Différence Elo (home - away)")

    # Forme spécifique (2)
    home_pts_last_5_at_home: Optional[float] = Field(None, description="Points moyens à domicile (5 derniers dom)")
    away_pts_last_5_away: Optional[float] = Field(None, description="Points moyens à l'extérieur (5 derniers ext)")

    # Fatigue (2)
    home_days_rest: Optional[float] = Field(None, description="Jours de repos équipe domicile")
    away_days_rest: Optional[float] = Field(None, description="Jours de repos équipe extérieur")

    # xG proxy (2)
    home_xg_proxy_last_5: Optional[float] = Field(None, description="Tirs cadrés moyens domicile (proxy xG)")
    away_xg_proxy_last_5: Optional[float] = Field(None, description="Tirs cadrés moyens extérieur (proxy xG)")


class PredictResponse(BaseModel):
    """Schéma de la réponse de prédiction."""
    home_team: str
    away_team: str
    prediction: str
    probabilities: dict[str, float]
    confidence: float
    model_version: str
    timestamp: str


class CheckoutRequest(BaseModel):
    user_id: str
    tier: str
    cycle: str # "monthly" | "yearly"

class CheckoutResponse(BaseModel):
    url: str

class HealthResponse(BaseModel):
    """Schéma de la réponse health check."""
    status: str
    version: str
    timestamp: str
    database: str
    model_loaded: bool
    features_count: int


# ============================================================
# Routes Stripe
# ============================================================

@app.post("/api/stripe/create-checkout-session", response_model=CheckoutResponse, tags=["Stripe"])
async def create_checkout_session(request: CheckoutRequest):
    """Crée une session de paiement Stripe pour un utilisateur."""
    try:
        price_id = PRICE_MAP.get(request.tier, {}).get(request.cycle)
        if not price_id:
            raise HTTPException(status_code=400, detail="Offre ou cycle invalide")

        site_url = os.getenv("NEXT_PUBLIC_SITE_URL", "http://localhost:3000")
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=f"{site_url}/dashboard?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{site_url}/pricing",
            metadata={
                "user_id": request.user_id,
                "tier": request.tier,
                "cycle": request.cycle
            }
        )

        return CheckoutResponse(url=checkout_session.url)
    except Exception as e:
        logger.error(f"Stripe Session Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stripe/webhook", tags=["Stripe"])
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    """Webhook pour gérer les événements Stripe (paiements, annulations)."""
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, stripe_webhook_secret
        )
    except Exception as e:
        logger.error(f"Webhook Signature Error: {e}")
        raise HTTPException(status_code=400, detail="Signature invalide")

    # Gestion de l'événement : Paiement réussi
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        user_id = metadata.get('user_id')
        tier = metadata.get('tier')
        cycle = metadata.get('cycle')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        if user_id and tier:
            db: Session = get_session()
            try:
                profile = db.query(Profile).filter(Profile.id == user_id).first()
                if profile:
                    profile.subscription_tier = tier
                    profile.billing_cycle = cycle
                    profile.stripe_customer_id = customer_id
                    profile.stripe_subscription_id = subscription_id
                    profile.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Abonnement débloqué pour {user_id} : {tier} ({cycle})")
                else:
                    logger.warning(f"Utilisateur {user_id} non trouvé dans la DB lors du webhook")
            except Exception as e:
                logger.error(f"Webhook DB Error: {e}")
                db.rollback()
            finally:
                db.close()

    # Gestion de l'événement : Abonnement supprimé / expiré
    if event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')

        if customer_id:
            db: Session = get_session()
            try:
                profile = db.query(Profile).filter(Profile.stripe_customer_id == customer_id).first()
                if profile:
                    profile.subscription_tier = "none"
                    profile.billing_cycle = None
                    profile.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Abonnement révoqué pour le client Stripe {customer_id}")
            except Exception as e:
                logger.error(f"Webhook DB Delete Error: {e}")
                db.rollback()
            finally:
                db.close()

    return {"status": "success"}

# ============================================================
# Routes Predictions
# ============================================================
@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Vérification de l'état de l'API et de ses dépendances."""
    db_status: str = "disconnected"
    try:
        from src.database.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="healthy",
        version="2.1.0",
        timestamp=datetime.utcnow().isoformat(),
        database=db_status,
        model_loaded=predictor_service.is_loaded,
        features_count=15,
    )


@app.post("/predict", response_model=PredictResponse, tags=["Predictions"])
def predict_match(request: PredictRequest) -> PredictResponse:
    """Prédiction via le modèle Deep Learning (15 features)."""
    logger.info(f"Prédiction : {request.home_team} vs {request.away_team}")

    # Valeurs par défaut si features absentes
    features: dict = {
        "home_pts_last_5": request.home_pts_last_5 or 1.5,
        "home_goals_scored_last_5": request.home_goals_scored_last_5 or 1.2,
        "home_goals_conceded_last_5": request.home_goals_conceded_last_5 or 1.0,
        "away_pts_last_5": request.away_pts_last_5 or 1.5,
        "away_goals_scored_last_5": request.away_goals_scored_last_5 or 1.0,
        "away_goals_conceded_last_5": request.away_goals_conceded_last_5 or 1.2,
        "home_elo": request.home_elo or 1500.0,
        "away_elo": request.away_elo or 1500.0,
        "elo_diff": request.elo_diff or (request.home_elo or 1500.0) - (request.away_elo or 1500.0),
        "home_pts_last_5_at_home": request.home_pts_last_5_at_home or 1.5,
        "away_pts_last_5_away": request.away_pts_last_5_away or 1.5,
        "home_days_rest": request.home_days_rest or 7.0,
        "away_days_rest": request.away_days_rest or 7.0,
        "home_xg_proxy_last_5": request.home_xg_proxy_last_5 or 4.0,
        "away_xg_proxy_last_5": request.away_xg_proxy_last_5 or 4.0,
    }

    # ---- Modèle PyTorch ----
    if predictor_service.is_loaded:
        try:
            result: dict = predictor_service.predict(**features)

            return PredictResponse(
                home_team=request.home_team,
                away_team=request.away_team,
                prediction=result["prediction"],
                probabilities=result["probabilities"],
                confidence=result["confidence"],
                model_version="pytorch-v2.0-elo",
                timestamp=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Erreur d'inférence PyTorch : {e}", exc_info=True)

    # ---- Fallback heuristique ----
    logger.info("Fallback heuristique actif")
    home_strength: float = min(features["home_pts_last_5"] / 3.0, 1.0)
    away_strength: float = min(features["away_pts_last_5"] / 3.0, 1.0)
    elo_bonus: float = (features["elo_diff"] / 400.0) * 0.1

    raw_home = home_strength + 0.1 + elo_bonus
    raw_away = away_strength
    raw_draw = 1.0 - abs(home_strength - away_strength)
    total = raw_home + raw_draw + raw_away

    prob_home = round(raw_home / total, 4)
    prob_draw = round(raw_draw / total, 4)
    prob_away = round(1.0 - prob_home - prob_draw, 4)

    probs = {"home_win": prob_home, "draw": prob_draw, "away_win": prob_away}
    prediction = max(probs, key=probs.get)  # type: ignore
    code_map = {"home_win": "H", "draw": "D", "away_win": "A"}

    return PredictResponse(
        home_team=request.home_team,
        away_team=request.away_team,
        prediction=code_map[prediction],
        probabilities=probs,
        confidence=round(max(probs.values()), 4),
        model_version="fallback-heuristic-elo",
        timestamp=datetime.utcnow().isoformat(),
    )


# ============================================================
# Route Frontend : Les 7 Prochains Jours (Live Pipeline)
# ============================================================
@app.get("/predictions/upcoming", tags=["Frontend"])
def get_upcoming_predictions(league: str = "Ligue 1") -> list[dict]:
    """
    Retourne les prédictions pour les 7 prochains jours.
    Incorpore les agendas ESPN, la Météo Open-Meteo et l'agrégation RSS.
    L'inférence est générée via le modèle PyTorch sur les dernières features en Base.
    """
    from src.ingestion.live_data import enrich_pipeline
    from src.database.database import get_session
    from src.database.models import Team, MatchRaw, MatchFeature

    logger.info(f"GET /predictions/upcoming — Ligue selectionnée : {league}")

    # 1. Récupération des données Live (ESPN/Mock + Météo + RSS)
    live_matches = enrich_pipeline(league)
    
    if not live_matches:
        return []

    # 2. Mapping avec la DB pour obtenir les features (Elo, Domicile/Exterieur Forme)
    session = get_session()
    results = []

    try:
        team_names = list(set([m["homeTeam"] for m in live_matches] + [m["awayTeam"] for m in live_matches]))
        
        # Mapping fuzzy: parfois "Paris SG" vs "Paris Saint Germain". Pour ce MVP, on fait du exact match.
        stmt_teams = select(Team.id, Team.name).where(Team.name.in_(team_names))
        team_map = {r.name: r.id for r in session.execute(stmt_teams).fetchall()}

        # Pour chaque match
        for idx, m in enumerate(live_matches):
            home_name = m["homeTeam"]
            away_name = m["awayTeam"]
            
            home_id = team_map.get(home_name)
            away_id = team_map.get(away_name)
            
            features = {
                "home_pts_last_5": 1.5, "home_goals_scored_last_5": 1.2, "home_goals_conceded_last_5": 1.0,
                "away_pts_last_5": 1.5, "away_goals_scored_last_5": 1.0, "away_goals_conceded_last_5": 1.2,
                "home_elo": 1500.0, "away_elo": 1500.0, "elo_diff": 0.0,
                "home_pts_last_5_at_home": 1.5, "away_pts_last_5_away": 1.5,
                "home_days_rest": 7.0, "away_days_rest": 7.0,
                "home_xg_last_5": 1.1, "home_xpts_last_5": 1.1,
                "away_xg_last_5": 1.1, "away_xpts_last_5": 1.1,
            }

            # Si on connait l'équipe Home, on demande sa dernière Feature Row
            if home_id:
                stmt_h = select(MatchFeature).join(MatchRaw, MatchFeature.match_id == MatchRaw.id).where(MatchRaw.home_team_id == home_id).order_by(desc(MatchRaw.date)).limit(1)
                row_h = session.execute(stmt_h).scalar()
                if row_h:
                    features["home_pts_last_5"] = float(row_h.home_pts_last_5) if row_h.home_pts_last_5 else 1.5
                    features["home_goals_scored_last_5"] = float(row_h.home_goals_scored_last_5) if row_h.home_goals_scored_last_5 else 1.2
                    features["home_goals_conceded_last_5"] = float(row_h.home_goals_conceded_last_5) if row_h.home_goals_conceded_last_5 else 1.0
                    features["home_elo"] = float(row_h.home_elo) if row_h.home_elo else 1500.0
                    features["home_pts_last_5_at_home"] = float(row_h.home_pts_last_5_at_home) if row_h.home_pts_last_5_at_home else 1.5
                    features["home_days_rest"] = float(row_h.home_days_rest) if row_h.home_days_rest else 7.0
                    features["home_xg_last_5"] = float(row_h.home_xg_last_5) if row_h.home_xg_last_5 else 1.1
                    features["home_xpts_last_5"] = float(row_h.home_xpts_last_5) if row_h.home_xpts_last_5 else 1.1

            # Pareil pour l'équipe Away
            if away_id:
                stmt_a = select(MatchFeature).join(MatchRaw, MatchFeature.match_id == MatchRaw.id).where(MatchRaw.away_team_id == away_id).order_by(desc(MatchRaw.date)).limit(1)
                row_a = session.execute(stmt_a).scalar()
                if row_a:
                    features["away_pts_last_5"] = float(row_a.away_pts_last_5) if row_a.away_pts_last_5 else 1.5
                    features["away_goals_scored_last_5"] = float(row_a.away_goals_scored_last_5) if row_a.away_goals_scored_last_5 else 1.0
                    features["away_goals_conceded_last_5"] = float(row_a.away_goals_conceded_last_5) if row_a.away_goals_conceded_last_5 else 1.2
                    features["away_elo"] = float(row_a.away_elo) if row_a.away_elo else 1500.0
                    features["away_pts_last_5_away"] = float(row_a.away_pts_last_5_away) if row_a.away_pts_last_5_away else 1.5
                    features["away_days_rest"] = float(row_a.away_days_rest) if row_a.away_days_rest else 7.0
                    features["away_xg_last_5"] = float(row_a.away_xg_last_5) if row_a.away_xg_last_5 else 1.1
                    features["away_xpts_last_5"] = float(row_a.away_xpts_last_5) if row_a.away_xpts_last_5 else 1.1

            features["elo_diff"] = features["home_elo"] - features["away_elo"]

            # 3. Inférence Modèle
            if predictor_service.is_loaded:
                try:
                    pred = predictor_service.predict(**features)
                    p1 = round(pred["probabilities"]["home_win"] * 100, 1)
                    pn = round(pred["probabilities"]["draw"] * 100, 1)
                    p2 = round(pred["probabilities"]["away_win"] * 100, 1)
                except Exception as e:
                    logger.error(f"Inference error: {e}")
                    p1, pn, p2 = 45.0, 25.0, 30.0
            else:
                p1, pn, p2 = 45.0, 25.0, 30.0

            # Recommandation IA
            if p1 > 55: recommendation = f"Victoire de {home_name} (Confiance Haute)"
            elif p2 > 55: recommendation = f"Victoire de {away_name} (Confiance Haute)"
            elif (p1 + pn) > 75: recommendation = f"{home_name} ou Nul (Double Chance)"
            elif (p2 + pn) > 75: recommendation = f"{away_name} ou Nul (Double Chance)"
            elif p1 > 40: recommendation = f"Victoire de {home_name} (Modéré)"
            elif p2 > 40: recommendation = f"Victoire de {away_name} (Modéré)"
            else: recommendation = "Prudence : Match incertain"

            # Parse DateTime format ISO 8601 from ESPN
            try:
                date_iso = m["date"]
                dt = datetime.strptime(date_iso.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
                
                # Jours : Lundi, Mardi, etc.
                days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
                day_name = days[dt.weekday()]
                date_fmt = f"{day_name} à {dt.strftime('%H:%M')}"
                
                if dt.date() == datetime.now().date():
                    date_fmt = f"Aujourd'hui à {dt.strftime('%H:%M')}"
                elif dt.date() == (datetime.now() + timedelta(days=1)).date():
                    date_fmt = f"Demain à {dt.strftime('%H:%M')}"
            except Exception:
                date_fmt = m["date"]

            results.append({
                "id": idx + 1,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "date": m["date"], # Keep original ISO string for frontend sorting and Date() parsing
                "dateFormatted": date_fmt, # Pass the friendly format explicitly
                "competition": league,
                "injuries": m["injuriesHome"] + m["injuriesAway"],
                "valueBet": {"active": False, "edge": 0, "target": None},
                "recommendation": recommendation,
                "probs": {"p1": p1, "pn": pn, "p2": p2},
                "details": {
                    "formHome": round(min(features["home_pts_last_5"] / 3.0, 1.0), 2),
                    "formAway": round(min(features["away_pts_last_5"] / 3.0, 1.0), 2),
                    "weatherCode": m["weatherCode"],
                    "injuriesCountHome": m["injuriesCountHome"],
                    "injuriesCountAway": m["injuriesCountAway"],
                    "homeElo": round(features["home_elo"]),
                    "awayElo": round(features["away_elo"]),
                    "eloDiff": round(features["elo_diff"]),
                    "homeDaysRest": round(features["home_days_rest"]),
                    "awayDaysRest": round(features["away_days_rest"]),
                },
            })

        logger.info(f"Retour de {len(results)} prédictions LIVE pour le frontend")
        return results

    except Exception as e:
        logger.error(f"Erreur GET /predictions/upcoming : {e}", exc_info=True)
        return []
    finally:
        session.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

