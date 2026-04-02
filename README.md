# 🤖 Next-Bet-AI — Neural Sports Prediction Engine (v2.0)

[![Next-Bet-AI](https://img.shields.io/badge/Version-2.0-orange?style=for-the-badge)](https://github.com/enizah35/Next-Bet-AI)
[![Stack](https://img.shields.io/badge/Stack-Next.js%20%7C%20FastAPI%20%7C%20PyTorch-blue?style=for-the-badge)](https://pytorch.org/)

**Next-Bet-AI** est une plateforme SaaS de pointe dédiée à l'analyse prédictive de football (Ligue 1 & Premier League). Propulsion par un moteur de **Deep Learning PyTorch**, Next-Bet-AI traite des milliers de points de données (xG, Elo, forme, météo, blessures) pour identifier les **Value Bets** avec une précision mathématique.

---

## 🌟 Fonctionnalités Clés

- **🧠 Neural Engine (PyTorch)** : Modèle de Deep Learning entraîné sur 10 ans de données Understat/ESPN. Architecture optimisée pour la classification probabiliste (Win/Draw/Loss).
- **📡 Pipeline Real-Time** : Ingestion asynchrone des données `Live` (Calendriers ESPN, Météo Open-Meteo, Alertes Presse RSS RMC/BBC).
- **📊 Méthodologie xG / xPts** : Intégration profonde des métriques Understat pour capturer la performance réelle au-delà du score final.
- **💰 Détection de Value Bets** : Algorithme comparant les probabilités IA aux cotes bookmakers pour isoler l'avantage statistique (Edge).
- **🔐 SaaS Ready** : Gestion complète des comptes utilisateurs, authentification via **Supabase Auth**, et gestion des abonnements (Profile & Forfaits).
- **🖥 Dashboard Premium** : Interface Next.js réactive, design **Glassmorphism**, mode sombre dynamique et prédictions débloquables.

---

## 🏗 Stack Technique (v2.0)

| Composant | Technologie | Rôle |
| :--- | :--- | :--- |
| **Frontend** | [Next.js 14](https://nextjs.org/) (App Router) | Interface utilisateur & Dashboard SaaS |
| **Authentification** | [Supabase](https://supabase.com/) | Gestion sécurisée des sessions & profils |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) | API haute performance (Inférence & Data Pipeline) |
| **IA / ML** | [PyTorch](https://pytorch.org/) | Moteur de prédiction neuronal (MatchPredictor) |
| **Base de données** | [PostgreSQL](https://www.postgresql.org/) | Stockage des features historiques et calculs Elo |
| **Orchestration** | Apache Airflow | Automatisation des pipelines d'ingestion quotidiens |

---

## 🚀 Installation Rapide (Local)

### 1. Backend (API & Model)
```bash
# Activation de l'environnement
# .\.venv\Scripts\Activate.ps1 (Windows) ou source .venv/bin/activate (Unix)

# Installation des dépendances
pip install -r requirements.txt

# Lancement de l'API (Port 8000)
python -m src.api.main
```

### 2. Frontend (Dashboard)
```bash
cd frontend
npm install
npm run dev
```
Accès : `http://localhost:3000`

---

## 📂 Structure du projet (Consolidée)

```text
next-bet-ai/
├── src/
│   ├── api/          # Backend FastAPI (Routes & Inférence)
│   ├── model/        # Cœur IA (Architecture PyTorch & Entraînement)
│   ├── ingestion/    # Pipelines Live (ESPN, Weather, RSS)
│   ├── database/     # Modèles PostgreSQL & SQLAlchemy
│   ├── features/     # Feature Engineering (xG, Elo, Form)
│   └── utils/        # Mappings et helpers
├── frontend/         # Application Next.js SaaS
├── dags/             # Orchestration Airflow
└── docker-compose.yml
```

---

## 🛡 License & Contact
Projet sous licence MIT. Développé pour la recherche avancée en analyse de données sportives.

---
*Developed with ❤️ by the Next-Bet-AI Team.*
