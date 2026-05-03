"""
src/api/main.py
Backend FastAPI pour Next-Bet-AI.
Routes : /health (GET), /predict (POST)
Intègre le modèle PyTorch MatchPredictor avec 15 features avancées.
"""

import logging
import os
import secrets
import stripe
import time
import concurrent.futures
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import text, select, desc
from sqlalchemy.orm import Session

from src.model.predict import predictor_service
from src.database.database import get_session
from src.database.models import Profile

logger: logging.Logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("%s invalide, fallback=%s", name, default)
        return default
    return max(minimum, min(value, maximum))


def _split_env_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_origin(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


APP_ENV = os.getenv("APP_ENV", os.getenv("ENV", "development")).strip().lower()
IS_PRODUCTION = APP_ENV in {"prod", "production"}
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()

UPCOMING_CACHE_TTL_SECONDS = _env_int("UPCOMING_CACHE_TTL_SECONDS", 90, 5, 3600)
UPCOMING_STALE_TTL_SECONDS = _env_int("UPCOMING_STALE_TTL_SECONDS", 1800, 30, 86400)
UPCOMING_MAX_LIMIT = _env_int("UPCOMING_MAX_LIMIT", 300, 1, 500)
UPCOMING_PREWARM_LIMIT = _env_int("UPCOMING_PREWARM_LIMIT", 300, 1, UPCOMING_MAX_LIMIT)
UPCOMING_DEFAULT_LEAGUES = [
    item.strip()
    for item in os.getenv(
        "UPCOMING_DEFAULT_LEAGUES",
        "Champions League,Premier League,Championship,Ligue 1,Ligue 2,Bundesliga,2. Bundesliga,La Liga,La Liga 2,Serie A,Serie B,Eredivisie,Primeira Liga,Süper Lig,Belgian Pro League,Scottish Premiership",
    ).split(",")
    if item.strip()
]
_upcoming_cache: dict[str, tuple[float, list[dict]]] = {}
_upcoming_refresh_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="upcoming-live")
_upcoming_inflight: set[str] = set()
_upcoming_inflight_lock = threading.Lock()


def _build_allowed_origins() -> tuple[bool, list[str]]:
    configured = _split_env_csv(os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS"))
    allow_all = "*" in configured and not IS_PRODUCTION
    if "*" in configured and IS_PRODUCTION:
        logger.warning("CORS '*' ignore en production. Configure CORS_ALLOWED_ORIGINS.")

    origins = [
        normalized
        for normalized in (_normalize_origin(origin) for origin in configured if origin != "*")
        if normalized
    ]
    site_origin = _normalize_origin(os.getenv("NEXT_PUBLIC_SITE_URL"))
    if site_origin:
        origins.append(site_origin)

    if not origins and not IS_PRODUCTION:
        origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ])

    return allow_all, sorted(set(origins))


CORS_ALLOW_ALL, CORS_ALLOWED_ORIGINS = _build_allowed_origins()


def _upcoming_cache_key(league: str, fast: bool, limit: int) -> str:
    return f"{league}:{fast}:{limit}"


def _is_cache_fresh(key: str, ttl: int = UPCOMING_CACHE_TTL_SECONDS) -> bool:
    cached = _upcoming_cache.get(key)
    return bool(cached and time.time() - cached[0] < ttl)


def _schedule_upcoming_live_refresh(league: str, limit: int) -> bool:
    """Refresh live complet en arrière-plan, sans bloquer le rendu mobile."""
    key = _upcoming_cache_key(league, False, limit)
    if _is_cache_fresh(key):
        return False

    with _upcoming_inflight_lock:
        if key in _upcoming_inflight:
            return False
        _upcoming_inflight.add(key)

    def _refresh() -> None:
        try:
            logger.info("Refresh live complet planifié — %s", key)
            get_upcoming_predictions(league=league, fast=False, refresh=True, limit=limit, background=False)
        except Exception as exc:
            logger.warning("Refresh live complet échoué (%s): %s", key, exc)
        finally:
            with _upcoming_inflight_lock:
                _upcoming_inflight.discard(key)

    _upcoming_refresh_executor.submit(_refresh)
    return True


def _safe_upcoming_limit(limit: int) -> int:
    return max(1, min(limit, UPCOMING_MAX_LIMIT))


def _get_site_url() -> str:
    site_url = _normalize_origin(os.getenv("NEXT_PUBLIC_SITE_URL"))
    if site_url:
        return site_url
    if IS_PRODUCTION:
        raise HTTPException(status_code=500, detail="Configuration site manquante")
    return "http://localhost:3000"


def require_admin_api_key(
    x_admin_api_key: Optional[str] = Header(default=None, alias="x-admin-api-key"),
) -> None:
    expected = ADMIN_API_KEY or os.getenv("ADMIN_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=404, detail="Route admin desactivee")
    if not x_admin_api_key or not secrets.compare_digest(x_admin_api_key, expected):
        raise HTTPException(status_code=401, detail="Authentification admin requise")

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
    if os.getenv("UPCOMING_PREWARM_ON_STARTUP", "true").lower() == "true":
        try:
            scheduled = _schedule_upcoming_live_refresh("all", _safe_upcoming_limit(UPCOMING_PREWARM_LIMIT))
            logger.info("Prechauffage cache live complet au demarrage (scheduled=%s)", scheduled)
        except Exception as e:
            logger.warning("Prechauffage cache live complet ignore: %s", e)

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
    docs_url=None if IS_PRODUCTION and not _env_bool("ENABLE_API_DOCS", False) else "/docs",
    redoc_url=None if IS_PRODUCTION and not _env_bool("ENABLE_API_DOCS", False) else "/redoc",
    openapi_url=None if IS_PRODUCTION and not _env_bool("ENABLE_API_DOCS", False) else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if CORS_ALLOW_ALL else CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type", "stripe-signature", "x-admin-api-key"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if IS_PRODUCTION or request.url.scheme == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

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
    user_id: str = Field(..., min_length=1, max_length=128)
    tier: str = Field(..., pattern="^(ligue1|pl|ultimate)$")
    cycle: str = Field(..., pattern="^(monthly|yearly)$")

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
        if not stripe.api_key:
            raise HTTPException(status_code=503, detail="Paiement indisponible")

        price_id = PRICE_MAP.get(request.tier, {}).get(request.cycle)
        if not price_id:
            raise HTTPException(status_code=400, detail="Offre ou cycle invalide")

        site_url = _get_site_url()
        
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

        if not checkout_session.url:
            raise HTTPException(status_code=502, detail="Session de paiement invalide")

        return CheckoutResponse(url=checkout_session.url)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe Session Error: {e}")
        raise HTTPException(status_code=500, detail="Erreur creation session Stripe")

@app.post("/api/stripe/webhook", tags=["Stripe"])
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """Webhook pour gérer les événements Stripe (paiements, annulations)."""
    if not stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook Stripe non configure")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Signature manquante")

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
    background: bool = False,
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

    safe_limit = _safe_upcoming_limit(limit)
    cache_key = _upcoming_cache_key(league, fast, safe_limit)
    full_cache_key = _upcoming_cache_key(league, False, safe_limit)
    fast_cache_key = _upcoming_cache_key(league, True, safe_limit)
    now = time.time()
    cached = _upcoming_cache.get(cache_key)
    if cached and not refresh and now - cached[0] < UPCOMING_CACHE_TTL_SECONDS:
        logger.info(f"GET /predictions/upcoming — cache hit {cache_key}")
        return cached[1]

    if background:
        scheduled = _schedule_upcoming_live_refresh(league, safe_limit)
        full_cached = _upcoming_cache.get(full_cache_key)
        if full_cached and now - full_cached[0] < UPCOMING_STALE_TTL_SECONDS:
            logger.info(f"GET /predictions/upcoming - live cache {full_cache_key} (scheduled={scheduled})")
            return full_cached[1]

        fast_cached = _upcoming_cache.get(fast_cache_key)
        if fast_cached and now - fast_cached[0] < UPCOMING_STALE_TTL_SECONDS:
            logger.info(f"GET /predictions/upcoming - fallback cache {fast_cache_key} (scheduled={scheduled})")
            return fast_cached[1]

        logger.info("GET /predictions/upcoming - refresh live en arriere-plan demarre sans cache pret")
        return []

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

    # Filtre temporel : on retire les matchs ayant débuté il y a plus de 90 minutes
    from datetime import timezone
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)

    def _match_kickoff(m: dict) -> Optional[datetime]:
        raw = m.get("date")
        if not raw:
            return None
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    live_matches = [m for m in live_matches if (ko := _match_kickoff(m)) is None or ko >= cutoff]
    if not live_matches:
        _upcoming_cache[cache_key] = (time.time(), [])
        return []

    # Round-robin par ligue avant d'appliquer le cap, pour qu'aucune ligue ne soit affamée
    by_league: dict[str, list[dict]] = {}
    for m in live_matches:
        by_league.setdefault(m.get("competition", "?"), []).append(m)
    for lst in by_league.values():
        lst.sort(key=lambda x: _match_kickoff(x) or datetime.max.replace(tzinfo=timezone.utc))

    balanced: list[dict] = []
    league_order = list(by_league.keys())
    while len(balanced) < safe_limit and any(by_league[lg] for lg in league_order):
        for lg in league_order:
            if not by_league[lg]:
                continue
            balanced.append(by_league[lg].pop(0))
            if len(balanced) >= safe_limit:
                break
    live_matches = balanced

    # 1b. Cotes multi-marchés (par ligue)
    bookmaker_cache: dict = {}
    if not fast:
        odds_workers = max(1, min(6, len(leagues_to_fetch)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=odds_workers) as executor:
            future_to_league = {executor.submit(fetch_bookmaker_odds, lg): lg for lg in leagues_to_fetch}
            for future in concurrent.futures.as_completed(future_to_league):
                lg = future_to_league[future]
                try:
                    bookmaker_cache.update(future.result())
                except Exception as e:
                    logger.warning(f"Bookmaker odds fetch failed ({lg}): {e}")

    # 2. Mapping avec la DB pour obtenir les features (Elo, Domicile/Exterieur Forme)
    should_log_predictions = os.getenv("PREDICTION_LOG_ON_READ", "").lower() == "true"
    live_features_in_fast = os.getenv("LIVE_FEATURES_IN_FAST", "true").lower() == "true"
    live_injuries_in_fast = os.getenv("LIVE_INJURIES_IN_FAST", "false").lower() == "true"
    live_squads_in_fast = os.getenv("LIVE_SQUADS_IN_FAST", "false").lower() == "true"
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
            live_match_stats_in_fast = os.getenv("LIVE_MATCH_STATS_IN_FAST", "false").lower() == "true"
            if session and (not fast or live_match_stats_in_fast):
                try:
                    match_stats = predict_match_stats(home_name, away_name, session=session, league=competition)
                except Exception:
                    if session:
                        session.rollback()

            fixture_id = m.get("fixtureId")
            home_api_id = m.get("apiHomeTeamId")
            away_api_id = m.get("apiAwayTeamId")
            home_inj, away_inj = 0, 0
            home_squad, away_squad = {}, {}
            squad_adj = {"home": 0.0, "draw": 0.0, "away": 0.0}
            injury_details = {
                "source": "none",
                "home": {"count": 0, "players": []},
                "away": {"count": 0, "players": []},
            }
            if not fast or live_injuries_in_fast:
                try:
                    from src.ingestion.api_football import get_current_api_season, get_injuries_for_match
                    current_season = get_current_api_season()
                    home_inj, away_inj, injury_details = get_injuries_for_match(
                        home_name,
                        away_name,
                        competition,
                        current_season,
                        fixture_id=fixture_id,
                        home_api_id=home_api_id,
                        away_api_id=away_api_id,
                        return_details=True,
                    )
                    features["home_injured_count"] = float(home_inj)
                    features["away_injured_count"] = float(away_inj)
                    features["injury_diff"] = float(away_inj - home_inj)
                except Exception as ie:
                    logger.debug(f"Blessures live ignorées: {ie}")

            if not fast or live_squads_in_fast:
                try:
                    from src.features.squad_strength import get_match_squad_info, compute_squad_adjustment
                    from src.ingestion.api_football import get_current_api_season

                    current_season = get_current_api_season()
                    lineups_lookahead_hours = int(os.getenv("LIVE_LINEUPS_LOOKAHEAD_HOURS", "4"))
                    fetch_lineups = not fast
                    kickoff_value = (m.get("apiFootballFixture") or {}).get("kickoff") or m.get("date")
                    try:
                        kickoff_dt = datetime.fromisoformat(str(kickoff_value).replace("Z", "+00:00"))
                        ref_now = datetime.now(kickoff_dt.tzinfo) if kickoff_dt.tzinfo else datetime.now()
                        fetch_lineups = (
                            kickoff_dt >= ref_now - timedelta(hours=2)
                            and kickoff_dt <= ref_now + timedelta(hours=lineups_lookahead_hours)
                        )
                    except Exception:
                        fetch_lineups = not fast

                    home_squad, away_squad = get_match_squad_info(
                        home_name,
                        away_name,
                        league=competition,
                        season=current_season,
                        fixture_id=fixture_id,
                        home_api_id=home_api_id,
                        away_api_id=away_api_id,
                        fixture_injuries=injury_details,
                        fetch_lineups=fetch_lineups,
                    )
                    squad_adj = compute_squad_adjustment(home_squad, away_squad)
                except Exception as se:
                    logger.debug(f"Squad ajustement ignoré: {se}")
                    home_squad, away_squad = {}, {}

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
                        if not home_squad or not away_squad:
                            raise RuntimeError("no squad data")
                        p1 += squad_adj["home"]
                        pn += squad_adj["draw"]
                        p2 += squad_adj["away"]
                    except Exception as se:
                        logger.debug(f"Squad ajustement ignoré: {se}")

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

            # Bet Builder IA (avec cotes réelles Winamax/Betclic + effectifs)
            bet_builder = generate_bet_builder(
                match_stats,
                {"p1": p1, "pn": pn, "p2": p2},
                bookmaker_odds=match_bk_odds,
                home_team=home_name,
                away_team=away_name,
                availability={
                    "home": {
                        **(home_squad or {}),
                        "injuries_count": home_inj or m["injuriesCountHome"],
                    },
                    "away": {
                        **(away_squad or {}),
                        "injuries_count": away_inj or m["injuriesCountAway"],
                    },
                    "source": injury_details.get("source"),
                },
            )

            odds_home = match_odds["avg_h"] if match_odds else None
            odds_draw = match_odds["avg_d"] if match_odds else None
            odds_away = match_odds["avg_a"] if match_odds else None
            home_injury_names = [
                f"{home_name}: {player.get('name')}"
                for player in (injury_details.get("home", {}) or {}).get("players", [])
                if player.get("name")
            ]
            away_injury_names = [
                f"{away_name}: {player.get('name')}"
                for player in (injury_details.get("away", {}) or {}).get("players", [])
                if player.get("name")
            ]
            injury_alerts = (m.get("injuriesHome") or []) + (m.get("injuriesAway") or []) + home_injury_names + away_injury_names

            results.append({
                "id": idx + 1,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "homeLogo": m.get("homeLogo"),
                "awayLogo": m.get("awayLogo"),
                "date": m["date"],
                "dateFormatted": date_fmt,
                "competition": competition,
                "league": competition,
                "injuries": injury_alerts,
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
                    "fixtureId": fixture_id,
                    "homeEspnId": m.get("homeEspnId"),
                    "awayEspnId": m.get("awayEspnId"),
                    "lineupsAvailable": bool(home_squad.get("lineup_confirmed") or away_squad.get("lineup_confirmed")),
                    "injuriesSource": injury_details.get("source"),
                    "injuriesCountHome": home_inj or m["injuriesCountHome"],
                    "injuriesCountAway": away_inj or m["injuriesCountAway"],
                    "homeMissingPlayers": (home_squad.get("missing_players") or [])[:5],
                    "awayMissingPlayers": (away_squad.get("missing_players") or [])[:5],
                    "homeElo": round(features["home_elo"]),
                    "awayElo": round(features["away_elo"]),
                    "eloDiff": round(features["elo_diff"]),
                    "homeDaysRest": round(extra["home_days_rest"]),
                    "awayDaysRest": round(extra["away_days_rest"]),
                },
                "availability": {
                    "fixtureId": fixture_id,
                    "fixture": m.get("apiFootballFixture") or {},
                    "injuries": injury_details,
                    "homeSquad": home_squad,
                    "awaySquad": away_squad,
                    "squadAdjustment": squad_adj,
                },
                "h2h": h2h,
                "liveStatus": {
                    "mode": "fast" if fast else "full",
                    "generatedAt": datetime.utcnow().isoformat(),
                    "oddsLoaded": bool(match_odds),
                    "bookmakerMarketsLoaded": bool(match_bk_odds),
                    "statsLoaded": bool(session and (not fast or live_match_stats_in_fast)),
                    "injuriesLoaded": injury_details.get("source") not in (None, "none"),
                    "lineupsLoaded": bool(home_squad.get("lineup_confirmed") or away_squad.get("lineup_confirmed")),
                },
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


@app.get("/predictions/upcoming/full-cached", tags=["Frontend"])
def get_upcoming_predictions_full_cached(
    league: str = "all",
    limit: int = 40,
    refresh: bool = False,
    wait: bool = False,
) -> list[dict]:
    """
    Return a full live payload from cache, with fallback to the fast cache
    while the heavy refresh is still warming up.
    """
    safe_limit = _safe_upcoming_limit(limit)
    cache_key = _upcoming_cache_key(league, False, safe_limit)
    fast_cache_key = _upcoming_cache_key(league, True, safe_limit)
    now = time.time()
    cached = _upcoming_cache.get(cache_key)

    if cached and not refresh and now - cached[0] < UPCOMING_CACHE_TTL_SECONDS:
        logger.info("GET /predictions/upcoming/full-cached - fresh cache %s", cache_key)
        return cached[1]

    scheduled = _schedule_upcoming_live_refresh(league, safe_limit)
    if cached and now - cached[0] < UPCOMING_STALE_TTL_SECONDS:
        logger.info(
            "GET /predictions/upcoming/full-cached - stale cache %s (scheduled=%s)",
            cache_key,
            scheduled,
        )
        return cached[1]

    if wait and _env_bool("ALLOW_PUBLIC_BLOCKING_REFRESH", False):
        logger.info("GET /predictions/upcoming/full-cached - cold blocking refresh %s", cache_key)
        return get_upcoming_predictions(
            league=league,
            fast=False,
            refresh=True,
            limit=safe_limit,
            background=False,
        )

    # Fallback : si le cache full n'est pas prêt, on tente le cache fast (frais ou stale).
    fast_cached = _upcoming_cache.get(fast_cache_key)
    if fast_cached and now - fast_cached[0] < UPCOMING_STALE_TTL_SECONDS:
        logger.info(
            "GET /predictions/upcoming/full-cached - fast cache fallback %s (scheduled=%s)",
            fast_cache_key,
            scheduled,
        )
        return fast_cached[1]

    # Aucun cache disponible : on calcule le payload fast en bloquant (rapide,
    # quelques secondes) plutôt que de renvoyer une liste vide.
    logger.info(
        "GET /predictions/upcoming/full-cached - cold fast fetch %s (scheduled=%s)",
        fast_cache_key,
        scheduled,
    )
    return get_upcoming_predictions(
        league=league,
        fast=True,
        refresh=False,
        limit=safe_limit,
        background=False,
    )


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
        return {"tips": [], "count": 0, "error": "Erreur interne"}
    finally:
        session.close()


# ============================================================
# Routes Admin
# ============================================================
class PredictionUpdateRequest(BaseModel):
    actual_result: Optional[str] = Field(None, pattern="^(H|D|A)$", description="H, D ou A")
    actual_home_goals: Optional[int] = Field(None, ge=0, le=30)
    actual_away_goals: Optional[int] = Field(None, ge=0, le=30)
    is_won: Optional[bool] = Field(None)


@app.get("/admin/predictions", tags=["Admin"])
def admin_get_predictions(
    limit: int = 200,
    offset: int = 0,
    _: None = Depends(require_admin_api_key),
) -> dict:
    """Retourne toutes les prédictions pour la page admin."""
    from src.database.database import get_session
    from src.database.models import PredictionLog
    from sqlalchemy import select, func, desc

    session = get_session()
    try:
        total = session.execute(select(func.count(PredictionLog.id))).scalar() or 0
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)
        stmt = select(PredictionLog).order_by(desc(PredictionLog.match_date)).limit(safe_limit).offset(safe_offset)
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
        raise HTTPException(status_code=500, detail="Erreur admin interne")
    finally:
        session.close()


@app.post("/admin/predictions/{prediction_id}", tags=["Admin"])
def admin_update_prediction(
    prediction_id: int,
    body: PredictionUpdateRequest,
    _: None = Depends(require_admin_api_key),
) -> dict:
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
        raise HTTPException(status_code=500, detail="Erreur admin interne")
    finally:
        session.close()


@app.post("/admin/retrain", tags=["Admin"])
def admin_retrain(_: None = Depends(require_admin_api_key)) -> dict:
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
        raise HTTPException(status_code=500, detail="Erreur admin interne")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=_env_int("API_PORT", 8000, 1, 65535),
        reload=_env_bool("UVICORN_RELOAD", False),
    )
