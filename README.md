# 🤖 Next-Bet-AI - Expert Trading Engine

![Next-Bet-AI Logo](assets/logo.png)

**Next-Bet-AI** est une plateforme de trading et d'analyse prédictive de nouvelle génération. En combinant le **Scraping Real-Time**, le **Deep Learning (XGBoost/PyTorch)** et la **Détection d'Anomalies (Value Bets)**, elle identifie les opportunités de paris sportifs les plus rentables sur le marché du football (Ligue 1, Premier League).

---

## 🌟 Fonctionnalités Clés

- **🛠 Pipeline de Données Live** : Récupération asynchrone des derniers calendriers (ESPN/FBref), de la météo des stades (Open-Meteo) et des alertes blessures/presse (Flux RSS BBC/RMC).
- **🧠 IA "Deep Learning Engine"** : Moteurs de prédictions basés initialement sur **XGBoost** évoluant vers des architectures neuronales complexes (**PyTorch**) entraînés sur 10 ans d'historique.
- **💰 Détection de Value Bets** : Comparaison intelligente entre les probabilités de l'IA et les cotes réelles des bookmakers pour isoler un avantage statistique (> 10% Edge).
- **🖥 Dashboard Premium** : Interface Ultra-Réactive avec design **Glassmorphism**, animations fluides et analyse détaillée de chaque match.
- **🛡 Pari Conseillé "Double Chance"** : Stratégie decisionnelle sécurisée pour minimiser les risques.

---

## 🏗 Stack Technique

| Layer | Technologie |
| :--- | :--- |
| **Frontend** | [Next.js 14](https://nextjs.org/) (React), Vanilla CSS (Glassmorphism design) |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) (Python), Uvicorn |
| **Database** | SQLite (PostgreSQL compatible) |
| **AI / ML** | [XGBoost](https://xgboost.ai/), [PyTorch](https://pytorch.org/), Scikit-Learn |
| **Scraping** | HTTPX, BeautifulSoup4, XML Parser |
| **Pipeline** | Apache Airflow |

---

## 🚀 Installation & Lancement

### 1. Prérequis
- Python 3.10+
- Node.js 18+
- Un environnement virtuel Python (`venv`)

### 2. Installation du Backend
```bash
# Se placer à la racine
python -m venv .venv
.\.venv\Scripts\Activate.ps1 # Windows
source .venv/bin/activate # Mac/Linux

pip install -r requirements.txt

# Lancer l'API
uvicorn api.main:app --reload
```

### 3. Installation du Frontend
```bash
cd frontend
npm install
npm run dev
```

### 4. Entraînement Initial (Optionnel)
```bash
python ml_model/train.py  # Entraîne le modèle XGBoost sur la base historique
```

---

## 📂 Structure du Projet

- `/api` : Serveur FastAPI et logique de trading.
- `/frontend` : Application Next.js.
- `/ml_model` : Architecture des modèles IA, scripts d'entraînement et d'inférence.
- `/scrapers` : Moteurs de collecte de données (Météo, RSS, Stats historiques).
- `/airflow` : Orchestration des tâches de mise à jour quotidienne.

---

## 🛡 License
Ce projet est sous licence MIT. Pour un usage commercial intensif, veuillez nous contacter.

---
*Developed with ❤️ for the future of sports analytics.*
