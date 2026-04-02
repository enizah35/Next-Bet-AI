# 🤖 Next-Bet-AI - Expert Trading Engine (v3.0)

![Next-Bet-AI Logo](assets/logo.png)

**Next-Bet-AI** est une plateforme de trading et d'analyse prédictive de nouvelle génération pour le football (Ligue 1, Premier League). En combinant le **Scraping Real-Time**, le **Deep Learning (PyTorch)** et la **Détection d'Anomalies (Value Bets)**, l'intelligence artificielle y identifie les opportunités de paris sportifs les plus rentables.

L'objectif du système est de dépasser substantiellement la baseline globale du marché (qui situe la probabilité native d'une victoire à domicile autour de 45%). Dans sa version actuelle (V3), Next-Bet-AI a atteint avec succès la barre critique des **55.3% d'Accuracy** en test clos.

---

## 🌟 Fonctionnalités Clés et Ingénierie

- **🛠 Pipeline de Données Live Avancé** : Récupération asynchrone des derniers calendriers historiques et futurs via ESPN et API Football, avec synchronisation dynamique de la météo des stades (Open-Meteo) et intégration des alertes blessures/presse (Flux RSS BBC/RMC pour EPL & L1).
- **📊 Intégration Understat (xG & xPts)** : Le cœur mathématique se nourrit massivement aux métriques avancées d'**Expected Goals** (xG) et **Expected Points** (xPts) moissonnées asynchronement sur Understat pour la dernière décennie. Ces indicateurs surpassent le simple comptage de buts pour une modélisation purement probabiliste.
- **🧠 Moteurs "Deep Learning" (PyTorch)** : Initialement basé sur de grands réseaux résiduels, le système V3 s'est purifié autour d'une architecture Linéaire ultra-rapide et parfaitement étudiée pour les variables tabulaires. En retirant le bruit et le déséquilibre imposés de classe, les inférences sont tranchantes.
- **💰 Détection de Value Bets** : Comparaison intelligente entre les probabilités certifiées de l'IA et les cotes réelles des bookmakers (Bet365 / Pinnacle) pour isoler le vrai *Edge*.
- **🖥 Dashboard Premium** : Interface Next.js Ultra-Réactive avec un design **Glassmorphism**, des animations fluides, un sélecteur dynamique de ligues et une modale d'insight temps-réel (Météo/News).

---

## 🏗 Stack Technique Orientée V3

| Layer | Technologie | Détails |
| :--- | :--- | :--- |
| **Frontend** | [Next.js 14](https://nextjs.org/) (React) | Vanilla CSS avec variables globales, flexiblité Glassmorphism |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) (Python) | Architecture ASGI, Uvicorn, Modèles Pydantic stricts |
| **Database** | PostgreSQL | Interfacé avec SQLAlchemy 2.0 (ORM) et migrations fluides |
| **Data Eng & ML** | [PyTorch](https://pytorch.org/), Pandas | Algorithme Linéaire PyTorch, Imputation Statistique, Rolling Windows |
| **Scraping** | `aiohttp`, `understat`, `feedparser` | Extractions massivement asynchrones (aiohttp) et Parser XML |
| **Orchestration** | Apache Airflow (Docker) | Jobs quotidiens sous environnement Python 3.12 |

---

## 🚀 Installation & Lancement Rapide (Local)

### 1. Prérequis
- Python 3.10+ (Recommandation : 3.12 pour compatibilité optimale Airflow)
- Node.js 18+
- Base de données PostgreSQL locale (ou Docker Compose)

### 2. Démarrage de l'Environnement Backend
```bash
# Activation de l'environnement virtuel Python
python -m venv .venv
source .venv/bin/activate       # Mac/Linux
# .\.venv\Scripts\Activate.ps1  # Windows

# Installation des dépendances du projet
pip install -r requirements.txt

# Optionnel (Si Base de données vide) - Lancement de l'Ingestion 
python src/ingestion/live_data.py
python src/ingestion/load_understat.py

# Démarrage de l'API FastAPI (Port 8000)
python -m src.api.main
```

### 3. Démarrage du Dashboard Frontend
```bash
cd frontend
npm install
npm run dev
```
L'interface sera accessible de manière fluide sur `http://localhost:3000`.

### 4. Entraînement Deep Learning (Reproductibilité)
Un script complet est prêt à être relancé si vous souhaitez rafraîchir le scaler et les poids neuronaux après de nouvelles saisons de foot :
```bash
# Lance le Feature Engineering de reconstruction (.rolling(5))
python -m src.features.build_features

# Démarre l'entraînement PyTorch (Split automatique 85/10/5)
python -m src.model.train
```

---

## 📂 Structure Pédagogique du Projet

```text
next-bet-ai/
├── frontend/                 # Application React / Next.js
│   └── src/app/              # Glassmorphism views, Modales & Layouts 
├── src/
│   ├── api/                  # Routes FastAPI, gestionnaires HTTP Live
│   ├── database/             # Modèles SQLAlchemy (Team, MatchRaw, MatchFeature)
│   ├── features/             # Feature Engineering (Calcul Elo, Form, xG Proxy part)
│   ├── ingestion/            # Pipelines ESPN, Understat, Seeders
│   ├── model/                # Architecture PyTorch (network.py), checkpt .pt et Inférence
│   └── utils/                # Mappings inter-API complexes
└── README.md
```

---

## 🛡 License
Ce projet est sous licence MIT. Pour un usage commercial intensif ou une redistribution sous la plateforme de paris d'un livreur existant, veuillez nous contacter formellement.

---
*Developed with ❤️ for the future of mathematically proven sports analytics.*
