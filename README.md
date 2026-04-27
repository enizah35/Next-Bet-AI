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

## 🚀 Démarrage Rapide (Installation & Lancement)

Le projet est divisé en deux parties : un backend (API FastAPI Python) et un frontend (Next.js App Router). **Il est fortement conseillé de lancer le backend avant le frontend**, car le frontend utilise les React Server Components (RSC) qui fetch les données de l'API au moment du build ou à la navigation.

### Prérequis
- **Python 3.11+**
- **Node.js 18+**
- **Base de données PostgreSQL** (Local ou hébergée via Supabase)

---

### 1. Cloner le Projet

```bash
git clone https://github.com/votre-user/next-bet-ai.git
cd next-bet-ai
```

---

### 2. Démarrer le Backend (API Python)

Le backend gère l'Intelligence Artificielle, l'ORM et les Webhooks de paiement.

```bash
# 1. Créer un environnement virtuel
python -m venv .venv

# 2. Activer l'environnement
# Sous Windows :
.venv\Scripts\Activate.ps1
# Sous macOS / Linux :
source .venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt
# (Pour Windows / PyTorch CPU léger : pip install torch --extra-index-url https://download.pytorch.org/whl/cpu)

# 4. Configurer les variables d'environnement (.env à la racine)
# DB_URL=postgresql://user:password@host:5432/nextbet
# STRIPE_SECRET_KEY=sk_test_...

# 5. Démarrer le serveur API
uvicorn src.api.main:app --reload --port 8000
```
L'API tourne maintenant sur [http://localhost:8000](http://localhost:8000). Vous pouvez explorer les routes via la documentation intégrée sur `http://localhost:8000/docs`.

---

### 3. Démarrer le Frontend (Next.js)

Le frontend est construit sous Next.js (App Router) et optimise les chargements via un rendu côté serveur.

```bash
# 1. Ouvrir un second terminal et aller dans /frontend
cd frontend

# 2. Installer les paquets
npm install

# 3. Configurer les variables d'environnement (frontend/.env.local)
# NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
# NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=eyJ...
# NEXT_PUBLIC_API_URL=http://localhost:8000    <-- Doit pointer sur le Backend lancé !

# 4. Lancer le serveur de développement
npm run dev

# (Optionnel) Pour tester le build de production :
# L'API locale doit être allumée car Next.js pré-compile les Server Components
npm run build && npm run start
```
L'application Web est désormais accessible sur [http://localhost:3000](http://localhost:3000).

---

## 🛠️ Scripts Annexes (Initialisation & Modèle)

Si vous installez le projet à partir de zéro, vous devrez initialiser la base de données et entraîner le modèle :

```bash
# S'assurer d'être à la racine avec .venv activé

# 1. Créer les tables SQL
python -c "from src.database.database import init_db; init_db()"

# 2. Insérer les 183 équipes (5 Ligues)
python -m src.database.seed_teams

# 3. Charger les historiques de matchs et Data AI
python -m src.ingestion.load_historical
python -m src.features.build_features

# 4. Entraîner le XGBoost
python -m src.model.train
```

---

## Ligues couvertes

- 🏴 Premier League (E0)
- 🇫🇷 Ligue 1 (F1)
- 🇩🇪 Bundesliga (D1)
- 🇪🇸 La Liga (SP1)
- 🇮🇹 Serie A (I1)

