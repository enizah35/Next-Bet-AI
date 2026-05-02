# Next-Bet-AI

Application de prediction football en phase de developpement.

Le projet combine un frontend Next.js, une API FastAPI, une base PostgreSQL/Supabase et une pipeline IA pour generer des analyses de matchs, probabilites 1N2, value bets, stats de match et AI Bet Builder.

Le deploiement public est volontairement mis de cote pour l'instant. L'objectif actuel est de stabiliser le front, la pipeline live et le modele de prediction avant de revenir vers Vercel, Hostinger ou une autre cible.

## Fonctionnalites

- Tableau d'analyses des matchs a venir.
- Predictions 1N2 avec probabilites domicile, nul, exterieur.
- Stats & AI Bet Builder avec selections par match, cotes estimees ou bookmakers si disponibles.
- Tips du jour tries par confiance.
- Historique de resultats et verification des predictions.
- Support multi-ligues live via ESPN.
- Enrichissement optionnel avec cotes live, blessures, effectifs et news.
- Modeles globaux et modeles specialises par ligue.

## Stack

| Couche | Technologie |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| UI | CSS custom, composants internes |
| Backend | FastAPI, Uvicorn, Pydantic |
| Base de donnees | PostgreSQL via Supabase, SQLAlchemy |
| Ingestion | football-data.co.uk, ESPN, Open-Meteo, RSS, API-Football optionnel |
| IA | PyTorch, XGBoost, LightGBM, scikit-learn |
| Paiements | Stripe, encore secondaire en phase dev |

## Structure

```text
next-bet-ai/
  frontend/                 App Next.js
    src/app/dashboard/      Analyses des matchs
    src/app/stats/          Stats & AI Bet Builder
    src/app/tips/           Tips du jour
    src/app/results/        Resultats et suivi
    src/components/         UI partagee, logos equipes, modales
  src/
    api/main.py             API FastAPI
    database/               Connexion DB et modeles SQLAlchemy
    ingestion/              Historique, live data, cotes, blessures
    features/               Feature engineering et bet builder
    model/                  Entrainement, inference, checkpoints
  scripts/                  Migrations, ingestion avancee et scripts utilitaires
```

## Ligues couvertes

La pipeline live sait interroger ces championnats :

- Premier League, Championship
- Ligue 1, Ligue 2
- Bundesliga, 2. Bundesliga
- La Liga, La Liga 2
- Serie A, Serie B
- Eredivisie
- Primeira Liga
- Super Lig
- Belgian Pro League
- Scottish Premiership

Les checkpoints specialises existent surtout pour les ligues prioritaires :

- `E0` Premier League
- `F1` Ligue 1
- `D1` Bundesliga
- `SP1` La Liga
- `I1` Serie A

## Variables d'environnement

Creer un fichier `.env` a la racine :

```env
DB_URL_POOLER=postgresql://...
API_FOOTBALL_KEY=...
ODDS_API_KEY=...
API_FOOTBALL_FIXTURES_IN_FAST=true
LIVE_INJURIES_IN_FAST=true
LIVE_SQUADS_IN_FAST=true
LIVE_LINEUPS_LOOKAHEAD_HOURS=4
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

Creer aussi `frontend/.env.local` :

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY=...
```

Notes :

- `DB_URL_POOLER` est recommande avec Supabase.
- `API_FOOTBALL_KEY` sert aux fixtures, blessures, effectifs et compos officielles proches du coup d'envoi.
- `LIVE_LINEUPS_LOOKAHEAD_HOURS` limite les appels compos officielles pour preserver le quota API-Football.
- `ODDS_API_KEY` active les vraies cotes live. Sans cette cle, l'app utilise un proxy Elo et des cotes estimees.
- Ne jamais commiter les fichiers `.env`.

## Installation backend

Depuis la racine du projet :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Initialiser la base :

```powershell
python -c "from src.database.database import init_db; init_db()"
```

Lancer l'API en local :

```powershell
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

Sur Windows, eviter `--reload` si un `BrokenPipeError` apparait.

API locale :

- `http://localhost:8000/health`
- `http://localhost:8000/docs`
- `http://localhost:8000/predictions/upcoming?fast=true&limit=5`

## Installation frontend

Dans un second terminal :

```powershell
cd frontend
npm install
npm run dev
```

Application locale :

```text
http://localhost:3000
```

Pages principales :

- `/dashboard` : analyses et predictions.
- `/stats` : stats par match et AI Bet Builder.
- `/tips` : tips du jour.
- `/results` : resultats et historique.
- `/pricing`, `/profile`, `/login`, `/register` : parcours compte/abonnement.

La page `/admin` n'est plus exposee dans le frontend.

## Pipeline donnees

Charger les historiques :

```powershell
python -m src.ingestion.load_historical
```

Construire les features :

```powershell
python -m src.features.build_features
```

La base contient ensuite :

- `teams`
- `matches_raw`
- `match_features`
- `prediction_logs`
- `profiles`

## Entrainement modele

Entrainer le modele global :

```powershell
python -m src.model.train
```

Entrainer une ligue precise :

```powershell
python -m src.model.train --league F1
python -m src.model.train --league E0
python -m src.model.train --league SP1
```

Entrainer plusieurs ligues specialisees :

```powershell
python -m src.model.train_leagues --leagues F1 E0 D1 SP1 I1
```

Premiere passe plus rapide :

```powershell
python -m src.model.train_leagues --all --quick
```

Les checkpoints sont sauvegardes dans :

```text
src/model/checkpoints/
src/model/checkpoints/leagues/<CODE_LIGUE>/
```

## API principale

| Methode | Route | Role |
|---|---|---|
| `GET` | `/health` | Etat API, DB, modele |
| `POST` | `/predict` | Prediction brute depuis features |
| `GET` | `/predictions/upcoming` | Matchs a venir + predictions + bet builder |
| `GET` | `/predictions/tips` | Tips du jour |
| `GET` | `/predictions/results` | Historique et statistiques de reussite |
| `POST` | `/predictions/verify` | Verification des resultats termines |

Exemple :

```powershell
Invoke-RestMethod "http://localhost:8000/predictions/upcoming?fast=true&limit=5"
```

## AI Bet Builder

Le bet builder est genere cote backend dans `src/features/bet_builder.py`.

Il utilise :

- probabilites du modele 1N2 ;
- estimation de buts via Poisson ;
- stats historiques recentes ;
- cotes bookmaker quand elles sont disponibles ;
- seuils de confiance par marche ;
- filtres de conflits pour eviter des combinaisons incoherentes.

Le frontend lit directement `match.betBuilder`. Il ne genere plus un faux combine fixe.

## Logos equipes

Les logos sont geres par `frontend/src/components/TeamLogo.tsx`.

Le composant utilise les IDs API-Football :

```text
https://media.api-sports.io/football/teams/<team_id>.png
```

Si un logo echoue, l'UI retombe sur un badge texte avec les initiales de l'equipe.

## Verification rapide

Backend :

```powershell
python -m py_compile src/api/main.py src/features/bet_builder.py src/features/match_stats.py
```

Frontend :

```powershell
cd frontend
npm run lint
```

Test API :

```powershell
Invoke-RestMethod "http://localhost:8000/predictions/upcoming?fast=true&limit=5"
```

## Etat actuel

Le projet est en phase dev.

Priorites court terme :

- stabiliser les noms d'equipes entre ESPN, football-data et API-Football ;
- brancher des cotes live fiables pour augmenter la qualite des value bets ;
- enrichir blessures/compositions probables ;
- suivre les resultats reels dans `prediction_logs` ;
- reentrainer les modeles par ligue avec feedback.

Le deploiement sera traite une fois le front et l'IA suffisamment stables.
