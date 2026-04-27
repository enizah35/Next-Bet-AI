"""
src/api/main.py
Backend FastAPI pour Next-Bet-AI.
Routes : /health (GET), /predict (POST)
Intègre le modèle PyTorch MatchPredictor avec 15 features avancées.
"""

import logging
import os
import stripe
import time
import concurrent.futures
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

UPCOMING_CACHE_TTL_SECONDS = int(os.getenv("UPCOMING_CACHE_TTL_SECONDS", "90"))
UPCOMING_DEFAULT_LEAGUES = [
    item.strip()
    for item in os.getenv(
        "UPCOMING_DEFAULT_LEAGUES",
        "Premier League,Championship,Ligue 1,Ligue 2,Bundesliga,2. Bundesliga,La Liga,La Liga 2,Serie A,Serie B,Eredivisie,Primeira Liga,SÃ¼per Lig,Belgian Pro League,Scottish Premiership",
    ).split(",")
    if item.strip()
]
_upcoming_cache: dict[str, tuple[float, list[dict]]] = {}

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

    # Création des tables manquantes (ex: prediction_logs)
    try:
        from src.database.database import init_db
        init_db()
        logger.info("Tables DB vérifiées / créées")
    except Exception as e:
        logger.warning(f"Impossible de vérifier les tables DB : {e}")

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
    allow_origins=["*"],
    allow_credentials=False,
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
    """Schéma de la requête de prédiction avec 31 features."""
    home_team: str = Field(..., description="Nom de l'équipe à domicile")
    away_team: str = Field(..., description="Nom de l'équipe à l'extérieur")
    league: Optional[str] = Field(None, description="Nom ou code de ligue, ex: Ligue 1 ou F1")

    # Probabilités implicites du marché (3)
    implied_home: Optional[float] = Field(None)
    implied_draw: Optional[float] = Field(None)
    implied_away: Optional[float] = Field(None)

    # Elo (3)
    home_elo: Optional[float] = Field(None)
    away_elo: Optional[float] = Field(None)
    elo_diff: Optional[float] = Field(None)

    # Forme générale domicile (3)
    home_pts_last_5: Optional[float] = Field(None)
    home_goals_scored_last_5: Optional[float] = Field(None)
    home_goals_conceded_last_5: Optional[float] = Field(None)

    # Forme générale extérieur (3)
    away_pts_last_5: Optional[float] = Field(None)
    away_goals_scored_last_5: Optional[float] = Field(None)
    away_goals_conceded_last_5: Optional[float] = Field(None)

    # Forme spécifique terrain (2)
    home_pts_last_5_at_home: Optional[float] = Field(None)
    away_pts_last_5_away: Optional[float] = Field(None)

    # Tirs cadrés (4)
    home_sot_last_5: Optional[float] = Field(None)
    away_sot_last_5: Optional[float] = Field(None)
    home_sot_conceded_last_5: Optional[float] = Field(None)
    away_sot_conceded_last_5: Optional[float] = Field(None)

    # xG proxy (2)
    home_xg_last_5: Optional[float] = Field(None)
    away_xg_last_5: Optional[float] = Field(None)

    # Repos / fatigue (2)
    home_days_rest: Optional[float] = Field(None)
    away_days_rest: Optional[float] = Field(None)

    # Série & momentum (4)
    home_unbeaten_streak: Optional[float] = Field(None)
    away_unbeaten_streak: Optional[float] = Field(None)
    home_momentum: Optional[float] = Field(None)
    away_momentum: Optional[float] = Field(None)

    # H2H (2)
    h2h_dominance: Optional[float] = Field(None)
    h2h_avg_goals: Optional[float] = Field(None)

    # Interactions engineered (3 — calculées côté API si non fournies)
    form_pts_diff: Optional[float] = Field(None)
    goal_diff_home: Optional[float] = Field(None)
    goal_diff_away: Optional[float] = Field(None)


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
        features_count=34,
    )


@app.post("/predict", response_model=PredictResponse, tags=["Predictions"])
def predict_match(request: PredictRequest) -> PredictResponse:
    """Prédiction via le modèle Deep Learning (14 features)."""
    logger.info(f"Prédiction : {request.home_team} vs {request.away_team}")

    # Passe toutes les features disponibles — les manquantes utilisent la moyenne d'entraînement
    features: dict = {k: v for k, v in request.model_dump().items()
                      if k not in ("home_team", "away_team", "league") and v is not None}

    # Calcul des interactions si les composantes sont disponibles mais l'interaction manque
    if "form_pts_diff" not in features and "home_pts_last_5" in features and "away_pts_last_5" in features:
        features["form_pts_diff"] = features["home_pts_last_5"] - features["away_pts_last_5"]
    if "goal_diff_home" not in features and "home_goals_scored_last_5" in features and "home_goals_conceded_last_5" in features:
        features["goal_diff_home"] = features["home_goals_scored_last_5"] - features["home_goals_conceded_last_5"]
    if "goal_diff_away" not in features and "away_goals_scored_last_5" in features and "away_goals_conceded_last_5" in features:
        features["goal_diff_away"] = features["away_goals_scored_last_5"] - features["away_goals_conceded_last_5"]

    # ---- Modèle PyTorch ----
    if predictor_service.is_loaded:
        try:
            result: dict = predictor_service.predict(league=request.league, **features)

            return PredictResponse(
                home_team=request.home_team,
                away_team=request.away_team,
                prediction=result["prediction"],
                probabilities=result["probabilities"],
                confidence=result["confidence"],
                model_version=f"pytorch-{result.get('model_scope', 'global')}-v2.2",
                timestamp=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"Erreur d'inférence PyTorch : {e}", exc_info=True)

    # ---- Fallback heuristique ----
    logger.info("Fallback heuristique actif")
    home_strength: float = min(features.get("home_pts_last_5", 1.5) / 3.0, 1.0)
    away_strength: float = min(features.get("away_pts_last_5", 1.5) / 3.0, 1.0)
    elo_bonus: float = (features.get("elo_diff", 0.0) / 400.0) * 0.1

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
def get_upcoming_predictions(
    league: str = "all",
    fast: bool = True,
    refresh: bool = False,
    limit: int = 40,
) -> list[dict]:
    """
    Retourne les prédictions pour les 7 prochains jours.
    Incorpore les agendas ESPN, la Météo Open-Meteo et l'agrégation RSS.
    L'inférence est générée via le modèle PyTorch sur les dernières features en Base.
    """
    from src.ingestion.live_data import enrich_pipeline
    from src.ingestion.live_odds import fetch_bookmaker_odds, get_match_bookmaker_odds
    from src.database.database import get_session
    from src.features.head_to_head import get_h2h_stats
    from src.features.match_stats import predict_match_stats
    from src.features.bet_builder import generate_bet_builder
    from datetime import datetime

    from src.ingestion.live_data import ESPN_LEAGUE_CODES

    safe_limit = max(1, min(limit, 80))
    cache_key = f"{league}:{fast}:{safe_limit}"
    now = time.time()
    cached = _upcoming_cache.get(cache_key)
    if cached and not refresh and now - cached[0] < UPCOMING_CACHE_TTL_SECONDS:
        logger.info(f"GET /predictions/upcoming — cache hit {cache_key}")
        return cached[1]

    logger.info(f"GET /predictions/upcoming — league={league} fast={fast} limit={safe_limit}")

    # 1. Récupération des données Live pour une ou toutes les ligues
    all_known_leagues = list(ESPN_LEAGUE_CODES.keys())
    leagues_to_fetch = UPCOMING_DEFAULT_LEAGUES if league == "all" else [league]
    leagues_to_fetch = [lg for lg in leagues_to_fetch if lg in all_known_leagues]
    if not leagues_to_fetch:
        leagues_to_fetch = UPCOMING_DEFAULT_LEAGUES

    live_matches: list[dict] = []
    max_workers = max(1, min(8, len(leagues_to_fetch)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_league = {
            executor.submit(enrich_pipeline, lg, fast=fast): lg
            for lg in leagues_to_fetch
        }
        for future in concurrent.futures.as_completed(future_to_league):
            lg = future_to_league[future]
            try:
                matches = future.result()
                for m in matches:
                    m.setdefault("competition", lg)
                live_matches.extend(matches)
            except Exception as e:
                logger.warning(f"enrich_pipeline({lg}) échoué : {e}")

    if not live_matches:
        _upcoming_cache[cache_key] = (time.time(), [])
        return []
    live_matches = live_matches[:safe_limit]

    # 1b. Cotes multi-marchés (par ligue)
    bookmaker_cache: dict = {}
    if not fast:
        for lg in leagues_to_fetch:
            try:
                bookmaker_cache.update(fetch_bookmaker_odds(lg))
            except Exception as e:
                logger.warning(f"Bookmaker odds fetch failed ({lg}): {e}")

    # 2. Mapping avec la DB pour obtenir les features (Elo, Domicile/Exterieur Forme)
    should_log_predictions = os.getenv("PREDICTION_LOG_ON_READ", "").lower() == "true"
    live_features_in_fast = os.getenv("LIVE_FEATURES_IN_FAST", "true").lower() == "true"
    live_injuries_in_fast = os.getenv("LIVE_INJURIES_IN_FAST", "false").lower() == "true"
    session = get_session() if (not fast or should_log_predictions or live_features_in_fast) else None
    results = []

    try:
        from src.features.feature_extractor import extract_match_features, FEATURE_DEFAULTS

        for idx, m in enumerate(live_matches):
            home_name = m["homeTeam"]
            away_name = m["awayTeam"]
            competition = m.get("competition", league)

            # Probabilités implicites depuis les cotes live
            match_odds = m.get("odds")
            if match_odds and session:
                odds_source = "live_bookmakers"
                features = extract_match_features(
                    home_name, away_name, session,
                    league=competition,
                    avg_h=match_odds.get("avg_h"),
                    avg_d=match_odds.get("avg_d"),
                    avg_a=match_odds.get("avg_a"),
                    implied_home=match_odds["implied_home"],
                    implied_draw=match_odds["implied_draw"],
                    implied_away=match_odds["implied_away"],
                    odds_mov_home=match_odds.get("odds_mov_home"),
                    odds_mov_draw=match_odds.get("odds_mov_draw"),
                )
            elif session:
                odds_source = "elo_proxy"
                features = extract_match_features(home_name, away_name, session, league=competition)
            else:
                odds_source = "fast_defaults_no_db"
                features = dict(FEATURE_DEFAULTS)

            # Alias pour l'affichage (compatibilité avec le reste du template)
            extra = {
                "home_pts_last_5": features.get("home_pts_last_5", 1.5),
                "home_goals_scored_last_5": features.get("home_goals_scored_last_5", 1.2),
                "away_goals_conceded_last_5": features.get("away_goals_conceded_last_5", 1.2),
                "home_days_rest": features.get("home_days_rest", 7.0),
                "away_days_rest": features.get("away_days_rest", 7.0),
            }

            # Sentiment des news
            home_sentiment = m.get("homeSentiment", 0.0)
            away_sentiment = m.get("awaySentiment", 0.0)

            # Confrontations directes (H2H)
            h2h = {"total_matches": 0, "home_wins": 0, "draws": 0, "away_wins": 0,
                   "home_win_pct": 0, "draw_pct": 0, "away_win_pct": 0,
                   "avg_goals_home": 0, "avg_goals_away": 0, "avg_total_goals": 0, "dominance": 0}
            if not fast:
                try:
                    h2h = get_h2h_stats(home_name, away_name, session=session)
                except Exception:
                    pass

            # Injection H2H dans les features pour le modèle (absorbé par **kwargs)
            # H2H stats gardées pour l'affichage dans la réponse

            # Stats prédites (goals, corners, cards, BTTS, O2.5)
            match_stats = {
                "predicted_goals": 2.5,
                "predicted_home_goals": 1.4,
                "predicted_away_goals": 1.1,
                "predicted_corners": 10.0,
                "predicted_cards": 4.0,
                "btts_pct": 50,
                "over25_pct": 50,
                "over15_pct": 65,
                "home_form": [],
                "away_form": [],
            }
            live_match_stats_in_fast = os.getenv("LIVE_MATCH_STATS_IN_FAST", "true").lower() == "true"
            if session and (not fast or live_match_stats_in_fast):
                try:
                    match_stats = predict_match_stats(home_name, away_name, session=session, league=competition)
                except Exception:
                    if session:
                        session.rollback()

            home_inj, away_inj = 0, 0
            home_squad, away_squad = {}, {}
            if not fast or live_injuries_in_fast:
                try:
                    from src.ingestion.api_football import get_injuries_for_match
                    current_year = datetime.now().year
                    home_inj, away_inj = get_injuries_for_match(home_name, away_name, competition, current_year)
                    features["home_injured_count"] = float(home_inj)
                    features["away_injured_count"] = float(away_inj)
                    features["injury_diff"] = float(away_inj - home_inj)
                except Exception as ie:
                    logger.debug(f"Blessures live ignorées: {ie}")

            # 3. Inférence Modèle
            if predictor_service.is_loaded:
                try:
                    pred = predictor_service.predict(league=competition, **features)
                    raw_probs = pred["probabilities"]
                    p1 = raw_probs["home_win"]
                    pn = raw_probs["draw"]
                    p2 = raw_probs["away_win"]

                    # --- Ajustement BERT sentiment (news pré-match) ---
                    try:
                        if fast:
                            raise RuntimeError("fast mode")
                        from src.features.news_nlp import get_team_news_sentiment, compute_news_adjustment
                        home_headlines = m.get("homeHeadlines", [])
                        away_headlines = m.get("awayHeadlines", [])
                        bert_home = get_team_news_sentiment(home_name, home_headlines)
                        bert_away = get_team_news_sentiment(away_name, away_headlines)
                        news_adj = compute_news_adjustment(bert_home, bert_away)
                        p1 += news_adj["home"]
                        pn += news_adj["draw"]
                        p2 += news_adj["away"]
                        home_sentiment = bert_home
                        away_sentiment = bert_away
                    except Exception as ne:
                        logger.debug(f"News NLP ajustement ignoré: {ne}")

                    # --- Ajustement effectif / composition ---
                    try:
                        if fast:
                            raise RuntimeError("fast mode")
                        from src.features.squad_strength import get_match_squad_info, compute_squad_adjustment
                        current_year = datetime.now().year
                        home_squad, away_squad = get_match_squad_info(
                            home_name, away_name, league=competition,
                            season=current_year,
                        )
                        squad_adj = compute_squad_adjustment(home_squad, away_squad)
                        p1 += squad_adj["home"]
                        pn += squad_adj["draw"]
                        p2 += squad_adj["away"]
                    except Exception as se:
                        logger.debug(f"Squad ajustement ignoré: {se}")
                        home_squad, away_squad = {}, {}

                    # Renormaliser pour que la somme = 1
                    total = p1 + pn + p2
                    if total > 0:
                        p1, pn, p2 = p1 / total, pn / total, p2 / total

                    p1 = round(p1 * 100, 1)
                    pn = round(pn * 100, 1)
                    p2 = round(p2 * 100, 1)

                except Exception as e:
                    logger.error(f"Inference error: {e}")
                    p1, pn, p2 = 45.0, 25.0, 30.0
                    home_squad, away_squad = {}, {}
            else:
                p1, pn, p2 = 45.0, 25.0, 30.0
                home_squad, away_squad = {}, {}

            # Recommandation IA
            if p1 > 55: recommendation = f"Victoire de {home_name} (Confiance Haute)"
            elif p2 > 55: recommendation = f"Victoire de {away_name} (Confiance Haute)"
            elif (p1 + pn) > 75: recommendation = f"{home_name} ou Nul (Double Chance)"
            elif (p2 + pn) > 75: recommendation = f"{away_name} ou Nul (Double Chance)"
            elif p1 > 40: recommendation = f"Victoire de {home_name} (Modéré)"
            elif p2 > 40: recommendation = f"Victoire de {away_name} (Modéré)"
            else: recommendation = "Prudence : Match incertain"

            # Complément sentiment dans la recommandation
            sentiment_note = ""
            if home_sentiment < -0.3:
                sentiment_note = f" ⚠️ Actualités négatives pour {home_name}"
            elif away_sentiment < -0.3:
                sentiment_note = f" ⚠️ Actualités négatives pour {away_name}"
            elif home_sentiment > 0.3:
                sentiment_note = f" 📈 Dynamique positive pour {home_name}"
            elif away_sentiment > 0.3:
                sentiment_note = f" 📈 Dynamique positive pour {away_name}"
            if sentiment_note:
                recommendation += sentiment_note

            # Parse DateTime format ISO 8601 from ESPN
            try:
                date_iso = m["date"]
                # Handle both "2026-04-12T15:15Z" and "2026-04-12T15:15:00Z"
                clean = date_iso.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean)
                
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

            # Value Bet detection (model probability vs bookmaker implied probability)
            value_bet = {"active": False, "edge": 0, "target": None, "selection": None, "bestOdds": None}
            if match_odds:
                model_probs = {"H": p1 / 100, "D": pn / 100, "A": p2 / 100}
                implied_probs = {"H": match_odds["implied_home"], "D": match_odds["implied_draw"], "A": match_odds["implied_away"]}
                best_odds_map = {"H": match_odds["best_odds"]["home"], "D": match_odds["best_odds"]["draw"], "A": match_odds["best_odds"]["away"]}
                label_map = {"H": "1", "D": "N", "A": "2"}
                selection_map = {"H": "Home", "D": "Draw", "A": "Away"}

                for outcome in ["H", "D", "A"]:
                    edge = (model_probs[outcome] - implied_probs[outcome]) * 100
                    if edge > 5.0:  # Seuil: 5% d'edge minimum
                        value_bet = {
                            "active": True,
                            "edge": round(edge, 1),
                            "target": label_map[outcome],
                            "selection": selection_map[outcome],
                            "bestOdds": best_odds_map[outcome],
                        }
                        break  # On prend le premier value bet trouvé

            # Cotes bookmaker pour ce match
            match_bk_odds = get_match_bookmaker_odds(home_name, away_name, bookmaker_cache)

            # Bet Builder IA (avec cotes réelles Winamax/Betclic)
            bet_builder = generate_bet_builder(match_stats, {"p1": p1, "pn": pn, "p2": p2}, bookmaker_odds=match_bk_odds)

            odds_home = match_odds["avg_h"] if match_odds else None
            odds_draw = match_odds["avg_d"] if match_odds else None
            odds_away = match_odds["avg_a"] if match_odds else None

            results.append({
                "id": idx + 1,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "date": m["date"],
                "dateFormatted": date_fmt,
                "competition": competition,
                "league": competition,
                "injuries": m["injuriesHome"] + m["injuriesAway"],
                "valueBet": value_bet,
                "recommendation": recommendation,
                "probs": {"p1": p1, "pn": pn, "p2": p2},
                "_features": features,  # stocké pour le feedback loop
                "stats": match_stats,
                "betBuilder": bet_builder,
                "sentiment": {
                    "home": home_sentiment,
                    "away": away_sentiment,
                    "diff": round(home_sentiment - away_sentiment, 3),
                    "homeHeadlines": m.get("homeHeadlines", []),
                    "awayHeadlines": m.get("awayHeadlines", []),
                },
                "odds": {
                    "source": odds_source,
                    "home": odds_home,
                    "draw": odds_draw,
                    "away": odds_away,
                    "h": odds_home,
                    "d": odds_draw,
                    "a": odds_away,
                    "bookmakers": match_odds["bookmakers_count"] if match_odds else 0,
                },
                "details": {
                    "formHome": round(min(extra["home_pts_last_5"] / 3.0, 1.0), 2),
                    "formAway": round(min(features["away_pts_last_5"] / 3.0, 1.0), 2),
                    "weatherCode": m["weatherCode"],
                    "injuriesCountHome": home_inj or m["injuriesCountHome"],
                    "injuriesCountAway": away_inj or m["injuriesCountAway"],
                    "homeElo": round(features["home_elo"]),
                    "awayElo": round(features["away_elo"]),
                    "eloDiff": round(features["elo_diff"]),
                    "homeDaysRest": round(extra["home_days_rest"]),
                    "awayDaysRest": round(extra["away_days_rest"]),
                },
                "h2h": h2h,
            })

        # Les logs DB sur une lecture frontend coûtent cher. On les active seulement explicitement.
        if should_log_predictions and session:
            from src.database.models import PredictionLog

            for res in results:
                bb = res.get("betBuilder", {})
                if not bb or not bb.get("selections"):
                    continue
                try:
                    match_dt = datetime.fromisoformat(res["date"].replace("Z", "+00:00"))
                except Exception:
                    match_dt = datetime.now()
                for sel in bb["selections"]:
                    try:
                        existing = session.execute(
                            select(PredictionLog).where(
                                PredictionLog.home_team == res["homeTeam"],
                                PredictionLog.away_team == res["awayTeam"],
                                PredictionLog.tip_type == sel["key"],
                            )
                        ).scalar()
                        if not existing:
                            try:
                                import json as _json
                                features_str = _json.dumps(res.get("_features", {}))[:4096]
                            except Exception:
                                features_str = None
                            session.add(PredictionLog(
                                home_team=res["homeTeam"],
                                away_team=res["awayTeam"],
                                league=res["competition"],
                                match_date=match_dt,
                                prediction=sel["label_fr"],
                                tip_type=sel["key"],
                                confidence=sel["confidence"],
                                odds=sel["odds"],
                                prob_home=res["probs"]["p1"],
                                prob_draw=res["probs"]["pn"],
                                prob_away=res["probs"]["p2"],
                                features_json=features_str,
                                created_at=datetime.now(),
                            ))
                    except Exception as ex:
                        logger.warning(f"Erreur log bet builder selection: {ex}")
            try:
                session.commit()
                logger.info(f"Bet builder selections logged for {len(results)} matches")
            except Exception as ex:
                logger.warning(f"Erreur commit bet builder logs: {ex}")
                session.rollback()

        logger.info(f"Retour de {len(results)} prédictions LIVE pour le frontend")
        _upcoming_cache[cache_key] = (time.time(), results)
        return results

    except Exception as e:
        logger.error(f"Erreur GET /predictions/upcoming : {e}", exc_info=True)
        return []
    finally:
        if session:
            session.close()


# ============================================================
# Route Tips du Jour
# ============================================================
@app.get("/predictions/tips", tags=["Frontend"])
def get_daily_tips(league: str = "all") -> dict:
    """
    Retourne les meilleurs tips IA du jour, triés par confiance.
    """
    from src.ingestion.live_data import enrich_pipeline
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from src.features.match_stats import predict_match_stats
    from src.features.bet_builder import generate_daily_tips
    from sqlalchemy import select, desc
    from datetime import datetime

    logger.info(f"GET /predictions/tips — league={league}")

    leagues_to_fetch = ["Ligue 1", "Premier League"] if league == "all" else [league]
    all_matches_data = []
    session = get_session()

    try:
        for lg in leagues_to_fetch:
            live_matches = enrich_pipeline(lg)
            if not live_matches:
                continue

            from src.features.feature_extractor import extract_match_features as _extract

            for m in live_matches:
                home_name = m["homeTeam"]
                away_name = m["awayTeam"]
                features = _extract(home_name, away_name, session, league=lg)

                # Prédiction IA
                p1, pn, p2 = 33.3, 33.4, 33.3
                if predictor_service.is_loaded:
                    try:
                        pred = predictor_service.predict(league=lg, **features)
                        p1 = round(pred["probabilities"]["home_win"] * 100, 1)
                        pn = round(pred["probabilities"]["draw"] * 100, 1)
                        p2 = round(pred["probabilities"]["away_win"] * 100, 1)
                    except Exception:
                        pass

                # Stats
                try:
                    stats = predict_match_stats(home_name, away_name, session)
                except Exception:
                    stats = {"btts_pct": 50, "over25_pct": 50, "over15_pct": 65, "predicted_goals": 2.5, "predicted_corners": 10, "predicted_cards": 4}

                all_matches_data.append({
                    "homeTeam": home_name,
                    "awayTeam": away_name,
                    "competition": lg,
                    "date": m["date"],
                    "probs": {"p1": p1, "pn": pn, "p2": p2},
                    "stats": stats,
                })

        tips = generate_daily_tips(all_matches_data, max_tips=15)

        # Log les tips dans PredictionLog pour le suivi
        for tip in tips:
            try:
                existing = session.execute(
                    select(PredictionLog).where(
                        PredictionLog.home_team == tip["homeTeam"],
                        PredictionLog.away_team == tip["awayTeam"],
                        PredictionLog.tip_type == tip["category"],
                    )
                ).scalar()
                if not existing:
                    log = PredictionLog(
                        home_team=tip["homeTeam"],
                        away_team=tip["awayTeam"],
                        league=tip.get("competition", ""),
                        match_date=datetime.fromisoformat(tip["date"]) if tip.get("date") else datetime.now(),
                        prediction=tip["tip"],
                        tip_type=tip["category"],
                        confidence=tip["confidence"],
                        odds=tip.get("odds"),
                        prob_home=tip.get("probs", {}).get("p1") if "probs" in tip else None,
                        prob_draw=tip.get("probs", {}).get("pn") if "probs" in tip else None,
                        prob_away=tip.get("probs", {}).get("p2") if "probs" in tip else None,
                        created_at=datetime.now(),
                    )
                    session.add(log)
            except Exception:
                pass
        try:
            session.commit()
        except Exception:
            session.rollback()

        return {"tips": tips, "count": len(tips), "generated_at": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Erreur GET /predictions/tips : {e}", exc_info=True)
        return {"tips": [], "count": 0, "error": str(e)}
    finally:
        session.close()


# ============================================================
# Route Résultats / Historique
# ============================================================
@app.get("/predictions/results", tags=["Frontend"])
def get_prediction_results() -> dict:
    """
    Retourne l'historique des prédictions et les statistiques de performance.
    """
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from sqlalchemy import select, func, desc

    logger.info("GET /predictions/results")
    session = get_session()

    try:
        # Stats globales
        total = session.execute(select(func.count(PredictionLog.id)).where(PredictionLog.is_won.isnot(None))).scalar() or 0
        won = session.execute(select(func.count(PredictionLog.id)).where(PredictionLog.is_won == True)).scalar() or 0
        lost = session.execute(select(func.count(PredictionLog.id)).where(PredictionLog.is_won == False)).scalar() or 0
        pending = session.execute(select(func.count(PredictionLog.id)).where(PredictionLog.is_won.is_(None))).scalar() or 0
        win_rate = round((won / total * 100), 1) if total > 0 else 0

        # Dernières prédictions
        stmt = select(PredictionLog).order_by(desc(PredictionLog.created_at)).limit(100)
        rows = session.execute(stmt).scalars().all()

        history = []
        # Grouper les bet builder par match (clé = date+home+away)
        bb_groups: dict[str, list] = {}
        BB_KEYS = {"match_result_home", "match_result_away", "double_chance_home",
                    "double_chance_away", "over_25", "over_15", "btts"}

        for r in rows:
            entry = {
                "id": r.id,
                "homeTeam": r.home_team,
                "awayTeam": r.away_team,
                "league": r.league,
                "matchDate": r.match_date.isoformat() if r.match_date else None,
                "prediction": r.prediction,
                "tipType": r.tip_type,
                "confidence": r.confidence,
                "odds": r.odds,
                "actualResult": r.actual_result,
                "actualScore": f"{r.actual_home_goals}-{r.actual_away_goals}" if r.actual_home_goals is not None else None,
                "isWon": r.is_won,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "verifiedAt": r.verified_at.isoformat() if r.verified_at else None,
            }
            history.append(entry)

            # Grouper les sélections bet builder
            if r.tip_type in BB_KEYS:
                match_key = f"{(r.match_date.strftime('%Y-%m-%d') if r.match_date else '')}__{r.home_team}__{r.away_team}"
                bb_groups.setdefault(match_key, []).append(entry)

        # Construire les combis bet builder
        bet_builders = []
        for key, selections in bb_groups.items():
            all_verified = all(s["isWon"] is not None for s in selections)
            all_won = all(s["isWon"] is True for s in selections)
            any_lost = any(s["isWon"] is False for s in selections)
            combined_odds = 1.0
            for s in selections:
                combined_odds *= (s["odds"] or 1.0)
            bet_builders.append({
                "matchKey": key,
                "homeTeam": selections[0]["homeTeam"],
                "awayTeam": selections[0]["awayTeam"],
                "league": selections[0]["league"],
                "matchDate": selections[0]["matchDate"],
                "actualScore": selections[0]["actualScore"],
                "selections": selections,
                "combinedOdds": round(combined_odds, 2),
                "isWon": True if (all_verified and all_won) else (False if any_lost else None),
            })

        return {
            "stats": {
                "total": total,
                "won": won,
                "lost": lost,
                "pending": pending,
                "winRate": win_rate,
            },
            "history": history,
            "betBuilders": bet_builders,
        }

    except Exception as e:
        logger.error(f"Erreur GET /predictions/results : {e}", exc_info=True)
        return {"stats": {"total": 0, "won": 0, "lost": 0, "pending": 0, "winRate": 0}, "history": []}
    finally:
        session.close()


# ============================================================
# POST /predictions/verify — Vérifier les résultats réels
# ============================================================
@app.post("/predictions/verify", tags=["Frontend"])
def verify_predictions() -> dict:
    """
    Vérifie les prédictions en attente en récupérant les scores réels
    depuis l'API football-data.org (matches terminés).
    Met à jour PredictionLog avec actual_result, actual_home_goals,
    actual_away_goals, is_won, verified_at.
    """
    import httpx
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from sqlalchemy import select
    from datetime import datetime, timedelta

    logger.info("POST /predictions/verify")
    session = get_session()
    verified_count = 0

    try:
        # Récupérer les prédictions en attente (is_won IS NULL)
        stmt = select(PredictionLog).where(PredictionLog.is_won.is_(None))
        pending = session.execute(stmt).scalars().all()

        if not pending:
            return {"verified": 0, "message": "Aucune prédiction en attente."}

        # Déterminer la plage de dates pour l'API
        dates = [p.match_date for p in pending if p.match_date]
        if not dates:
            return {"verified": 0, "message": "Aucune date de match trouvée."}

        min_date = min(dates) - timedelta(days=1)
        max_date = max(dates) + timedelta(days=1)

        # Fetch finished matches from football-data.org (free tier)
        api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
        headers = {"X-Auth-Token": api_key} if api_key else {}

        # Ligue 1 = code FL1, Premier League = PL
        league_codes = {"Ligue 1": "FL1", "Premier League": "PL"}
        all_finished: list[dict] = []

        for league_name, code in league_codes.items():
            try:
                url = f"https://api.football-data.org/v4/competitions/{code}/matches"
                params = {
                    "dateFrom": min_date.strftime("%Y-%m-%d"),
                    "dateTo": max_date.strftime("%Y-%m-%d"),
                    "status": "FINISHED",
                }
                resp = httpx.get(url, headers=headers, params=params, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("matches", []):
                        all_finished.append({
                            "homeTeam": m["homeTeam"]["name"],
                            "awayTeam": m["awayTeam"]["name"],
                            "homeGoals": m["score"]["fullTime"]["home"],
                            "awayGoals": m["score"]["fullTime"]["away"],
                            "date": m["utcDate"][:10],
                            "league": league_name,
                        })
                else:
                    logger.warning(f"football-data.org {code}: HTTP {resp.status_code}")
            except Exception as ex:
                logger.warning(f"football-data.org {code}: {ex}")

        if not all_finished:
            logger.info("Aucun match terminé trouvé via l'API.")
            return {"verified": 0, "message": "Aucun match terminé trouvé."}

        # Construire un index pour lookup rapide
        # Clé: (date YYYY-MM-DD, home_team_lower, away_team_lower)
        from difflib import SequenceMatcher

        def _normalize(name: str) -> str:
            return name.lower().strip().replace("fc ", "").replace(" fc", "").replace("paris saint-germain", "psg").replace("paris sg", "psg")

        finished_index: list[dict] = []
        for fm in all_finished:
            finished_index.append({
                **fm,
                "_home": _normalize(fm["homeTeam"]),
                "_away": _normalize(fm["awayTeam"]),
            })

        def _find_match(pred: PredictionLog) -> dict | None:
            pred_date = pred.match_date.strftime("%Y-%m-%d") if pred.match_date else ""
            pred_home = _normalize(pred.home_team)
            pred_away = _normalize(pred.away_team)

            for fm in finished_index:
                # Date doit être proche (±1 jour)
                if abs((datetime.strptime(fm["date"], "%Y-%m-%d") - datetime.strptime(pred_date, "%Y-%m-%d")).days) > 1:
                    continue
                # Fuzzy match sur les noms d'équipe
                home_ratio = SequenceMatcher(None, pred_home, fm["_home"]).ratio()
                away_ratio = SequenceMatcher(None, pred_away, fm["_away"]).ratio()
                if home_ratio > 0.6 and away_ratio > 0.6:
                    return fm
            return None

        # Vérifier chaque prédiction en attente
        for pred in pending:
            fm = _find_match(pred)
            if not fm:
                continue

            hg = fm["homeGoals"]
            ag = fm["awayGoals"]
            actual_result = "H" if hg > ag else ("A" if ag > hg else "D")

            pred.actual_home_goals = hg
            pred.actual_away_goals = ag
            pred.actual_result = actual_result
            pred.verified_at = datetime.now()

            # Déterminer si la prédiction est gagnée
            tip = pred.tip_type.lower() if pred.tip_type else ""
            prediction_val = (pred.prediction or "").lower().strip()

            # Bet builder keys
            if tip == "match_result_home":
                pred.is_won = actual_result == "H"
            elif tip == "match_result_away":
                pred.is_won = actual_result == "A"
            elif tip == "double_chance_home":
                pred.is_won = actual_result in ("H", "D")
            elif tip == "double_chance_away":
                pred.is_won = actual_result in ("A", "D")
            elif tip == "over_25":
                pred.is_won = (hg + ag) > 2.5
            elif tip == "over_15":
                pred.is_won = (hg + ag) > 1.5
            elif tip == "btts":
                pred.is_won = (hg > 0 and ag > 0)
            # Legacy tip types
            elif "double" in tip or "dbl" in tip:
                if "1" in prediction_val or "home" in prediction_val:
                    pred.is_won = actual_result in ("H", "D")
                elif "2" in prediction_val or "away" in prediction_val:
                    pred.is_won = actual_result in ("A", "D")
                else:
                    pred.is_won = False
            elif "btts" in tip:
                pred.is_won = (hg > 0 and ag > 0)
            elif "over" in tip and "2.5" in tip:
                pred.is_won = (hg + ag) > 2.5
            elif "over" in tip and "1.5" in tip:
                pred.is_won = (hg + ag) > 1.5
            elif "result" in tip or tip == "":
                pred.is_won = (prediction_val == actual_result.lower())
            else:
                pred.is_won = (prediction_val == actual_result.lower())

            verified_count += 1

        session.commit()
        logger.info(f"Vérification terminée: {verified_count} prédictions mises à jour")
        return {"verified": verified_count, "message": f"{verified_count} prédiction(s) vérifiée(s)."}

    except Exception as e:
        session.rollback()
        logger.error(f"Erreur POST /predictions/verify : {e}", exc_info=True)
        return {"verified": 0, "error": str(e)}
    finally:
        session.close()


# ============================================================
# Routes Admin
# ============================================================
class PredictionUpdateRequest(BaseModel):
    actual_result: Optional[str] = Field(None, description="H, D ou A")
    actual_home_goals: Optional[int] = Field(None)
    actual_away_goals: Optional[int] = Field(None)
    is_won: Optional[bool] = Field(None)


@app.get("/admin/predictions", tags=["Admin"])
def admin_get_predictions(limit: int = 200, offset: int = 0) -> dict:
    """Retourne toutes les prédictions pour la page admin."""
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from sqlalchemy import select, func, desc

    session = get_session()
    try:
        total = session.execute(select(func.count(PredictionLog.id))).scalar() or 0
        stmt = select(PredictionLog).order_by(desc(PredictionLog.match_date)).limit(limit).offset(offset)
        rows = session.execute(stmt).scalars().all()
        predictions = [
            {
                "id": r.id,
                "homeTeam": r.home_team,
                "awayTeam": r.away_team,
                "league": r.league,
                "matchDate": r.match_date.isoformat() if r.match_date else None,
                "prediction": r.prediction,
                "tipType": r.tip_type,
                "confidence": r.confidence,
                "odds": r.odds,
                "probHome": r.prob_home,
                "probDraw": r.prob_draw,
                "probAway": r.prob_away,
                "actualResult": r.actual_result,
                "actualHomeGoals": r.actual_home_goals,
                "actualAwayGoals": r.actual_away_goals,
                "isWon": r.is_won,
                "createdAt": r.created_at.isoformat() if r.created_at else None,
                "verifiedAt": r.verified_at.isoformat() if r.verified_at else None,
                "hasFeaturesJson": r.features_json is not None,
            }
            for r in rows
        ]
        return {"predictions": predictions, "total": total}
    except Exception as e:
        logger.error(f"Erreur GET /admin/predictions : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/admin/predictions/{prediction_id}", tags=["Admin"])
def admin_update_prediction(prediction_id: int, body: PredictionUpdateRequest) -> dict:
    """Met à jour manuellement une prédiction (résultat réel, victoire/défaite)."""
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from sqlalchemy import select

    session = get_session()
    try:
        pred = session.execute(select(PredictionLog).where(PredictionLog.id == prediction_id)).scalar()
        if not pred:
            raise HTTPException(status_code=404, detail="Prédiction non trouvée")

        if body.actual_result is not None:
            pred.actual_result = body.actual_result
        if body.actual_home_goals is not None:
            pred.actual_home_goals = body.actual_home_goals
        if body.actual_away_goals is not None:
            pred.actual_away_goals = body.actual_away_goals

        # Auto-compute is_won if we have result but not explicit is_won
        if body.is_won is not None:
            pred.is_won = body.is_won
        elif body.actual_result is not None and pred.tip_type:
            tip = pred.tip_type.lower()
            actual = body.actual_result
            hg = body.actual_home_goals or 0
            ag = body.actual_away_goals or 0
            prediction_val = (pred.prediction or "").lower()

            if tip == "match_result_home":
                pred.is_won = actual == "H"
            elif tip == "match_result_away":
                pred.is_won = actual == "A"
            elif tip == "double_chance_home":
                pred.is_won = actual in ("H", "D")
            elif tip == "double_chance_away":
                pred.is_won = actual in ("A", "D")
            elif tip == "over_25":
                pred.is_won = (hg + ag) > 2.5
            elif tip == "over_15":
                pred.is_won = (hg + ag) > 1.5
            elif tip == "btts":
                pred.is_won = (hg > 0 and ag > 0)
            elif "double" in tip:
                if "1" in prediction_val or "home" in prediction_val:
                    pred.is_won = actual in ("H", "D")
                elif "2" in prediction_val or "away" in prediction_val:
                    pred.is_won = actual in ("A", "D")
            else:
                pred.is_won = (prediction_val == actual.lower())

        pred.verified_at = datetime.utcnow()
        session.commit()
        return {"success": True, "id": prediction_id, "isWon": pred.is_won}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Erreur POST /admin/predictions/{prediction_id} : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/admin/retrain", tags=["Admin"])
def admin_retrain() -> dict:
    """Lance le réentraînement du meta-learner avec le feedback des prédictions vérifiées."""
    import subprocess, sys
    logger.info("POST /admin/retrain — lancement du réentraînement")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.retrain_with_feedback"],
            capture_output=True, text=True, timeout=300,
        )
        success = result.returncode == 0
        return {
            "success": success,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout — réentraînement trop long (>5min)"}
    except Exception as e:
        logger.error(f"Erreur POST /admin/retrain : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)

