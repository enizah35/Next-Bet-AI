---
title: Next Bet AI - Neural Performance
emoji: ⚽
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
---

# Next-Bet-AI ⚽

Plateforme de prédiction de matchs de football alimentée par l'Intelligence Artificielle.  
Combine des modèles XGBoost / Neural Network avec des features avancées (Elo, forme, tirs cadrés, cotes du marché) pour prédire les résultats (Victoire / Nul / Défaite) sur 5 ligues européennes.

---

## Stack Technique

| Couche | Technologie | Version |
|---|---|---|
| **Frontend** | Next.js (React, TypeScript) | 16.x |
| **UI / Animations** | Framer Motion | 12.x |
| **Auth & DB temps réel** | Supabase (Auth + PostgREST) | — |
| **Backend / API** | FastAPI (Python) | — |
| **ORM** | SQLAlchemy | 2.0+ |
| **Base de données** | PostgreSQL (Supabase Cloud) | 15+ |
| **Modèle IA principal** | XGBoost (gradient boosting) | 2.x |
| **Modèle IA secondaire** | PyTorch (MLP avec blocs résiduels) | 2.x |
| **Feature Engineering** | pandas, NumPy, scikit-learn | — |
| **Paiements** | Stripe (Checkout + Webhooks) | — |
| **Déploiement** | Docker → Hugging Face Spaces | — |

---

## Architecture du Projet

```
next-bet-ai/
├── frontend/                # App Next.js (TypeScript)
│   ├── app/                 # Pages (dashboard, pricing, login…)
│   ├── components/          # Composants React réutilisables
│   └── lib/                 # Client Supabase, helpers
├── src/
│   ├── api/main.py          # FastAPI — routes & endpoints
│   ├── database/
│   │   ├── database.py      # Connexion PostgreSQL (SQLAlchemy)
│   │   ├── models.py        # ORM : teams, matches_raw, match_features, profiles, prediction_logs
│   │   └── seed_teams.py    # Script de seed (183 équipes, 5 ligues)
│   ├── features/
│   │   └── build_features.py  # Feature engineering (Elo, forme, tirs, H2H)
│   ├── ingestion/
│   │   ├── live_data.py     # Données live (matchs, cotes, météo, sentiment)
│   │   ├── load_historical.py  # Import historique football-data.co.uk
│   │   └── load_understat.py   # Import xG depuis Understat
│   └── model/
│       ├── network.py       # Architecture NN (MatchPredictor)
│       ├── train.py         # Pipeline d'entraînement (NN + XGBoost + Stacking)
│       ├── predict.py       # Service d'inférence (14 features)
│       └── checkpoints/     # Modèles sauvegardés (.pt, .json, .pkl)
├── scripts/                 # Utilitaires (analyse, expérimentations, migrations)
├── Dockerfile               # Image Docker (Python 3.11, CPU)
└── requirements.txt
```

---

## Endpoints API

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/health` | Health check (DB, modèle, version) |
| `POST` | `/predict` | Prédiction sur 14 features (H/D/A + probabilités) |
| `GET` | `/predictions/upcoming` | Matchs à venir (7 jours) avec prédictions IA |
| `GET` | `/predictions/tips` | Tips du jour triés par confiance |
| `GET` | `/predictions/results` | Historique des prédictions + taux de réussite |
| `POST` | `/predictions/verify` | Vérification des résultats réels |
| `POST` | `/api/stripe/create-checkout-session` | Création de session Stripe |
| `POST` | `/api/stripe/webhook` | Webhook Stripe (paiements) |

---

## Modèle IA

**14 features** sélectionnées par importance XGBoost :

| Catégorie | Features |
|---|---|
| Cotes du marché (3) | `implied_home`, `implied_draw`, `implied_away` |
| Elo (3) | `home_elo`, `away_elo`, `elo_diff` |
| Forme (3) | `home_goals_conceded_last_5`, `away_goals_scored_last_5`, `away_pts_last_5` |
| Forme dom/ext (2) | `home_pts_last_5_at_home`, `away_pts_last_5_away` |
| Tirs cadrés (3) | `home_sot_last_5`, `away_sot_last_5`, `away_sot_conceded_last_5` |

**Pipeline** : XGBoost (depth=4) → ~56% accuracy sur 10 666 matchs (5 ligues × 15 saisons, split chronologique).

---

## Installation & Lancement

### Prérequis

- **Python** 3.11+
- **Node.js** 18+
- **PostgreSQL** (ou un projet Supabase)

### 1. Cloner le repo

```bash
git clone https://github.com/<votre-user>/next-bet-ai.git
cd next-bet-ai
```

### 2. Backend (FastAPI)

```bash
# Créer un environnement virtuel
python -m venv .venv

# Activer (Windows)
.venv\Scripts\Activate.ps1
# Activer (macOS/Linux)
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
# Pour PyTorch CPU uniquement :
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
```

### 3. Variables d'environnement

Créer un fichier `.env` à la racine :

```env
# Base de données PostgreSQL
DB_URL=postgresql://user:password@host:5432/nextbet

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_LIGUE1_MONTHLY=price_...
STRIPE_PRICE_LIGUE1_YEARLY=price_...
STRIPE_PRICE_PL_MONTHLY=price_...
STRIPE_PRICE_PL_YEARLY=price_...
STRIPE_PRICE_ULTIMATE_MONTHLY=price_...
STRIPE_PRICE_ULTIMATE_YEARLY=price_...

# APIs externes
FOOTBALL_DATA_API_KEY=...
ODDS_API_KEY=...

# URL du frontend
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

### 4. Initialiser la base de données

```bash
# Créer les tables
python -c "from src.database.database import init_db; init_db()"

# Seed des équipes (183 équipes, 5 ligues)
python -m src.database.seed_teams

# Charger les données historiques
python -m src.ingestion.load_historical

# Construire les features
python -m src.features.build_features
```

### 5. Entraîner le modèle

```bash
python -m src.model.train
```

Le checkpoint est sauvegardé dans `src/model/checkpoints/`.

### 6. Lancer le backend

```bash
uvicorn src.api.main:app --reload --port 8000
```

L'API est accessible sur `http://localhost:8000` (docs Swagger : `/docs`).

### 7. Frontend (Next.js)

```bash
cd frontend

# Installer les dépendances
npm install

# Créer frontend/.env.local
# NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
# NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=eyJ...
# NEXT_PUBLIC_API_URL=http://localhost:8000

# Lancer le dev server
npm run dev
```

Le frontend est accessible sur `http://localhost:3000`.

---

## Docker

```bash
# Build
docker build -t next-bet-ai .

# Run
docker run -p 7860:7860 --env-file .env next-bet-ai
```

---

## Scripts utilitaires

| Script | Commande | Description |
|---|---|---|
| Analyse DB | `python -m scripts.check_db` | Vérifier l'état de la base |
| Analyse data | `python -m scripts.analyze_data` | Stats sur les matchs/odds |
| Feature importance | `python -m scripts.analyze_importance` | Classement des features |
| Expérimentations | `python -m scripts.experiment_models` | Comparaison XGBoost / LightGBM |
| Test inférence | `python -m scripts.test_inference` | Tester le modèle en local |

---

## Ligues couvertes

- 🏴 Premier League (E0)
- 🇫🇷 Ligue 1 (F1)
- 🇩🇪 Bundesliga (D1)
- 🇪🇸 La Liga (SP1)
- 🇮🇹 Serie A (I1)
