# Next-Bet-AI — Comment fonctionne le système de prédiction

## Vue d'ensemble

```
Données historiques ──► Feature Engineering ──► Entraînement ──► Modèle
                                                                     │
Données live (ESPN/cotes) ──► Extraction features ──────────────────► Inférence
                                                                     │
                                                               Prédiction (H/D/A)
                                                               + Stats (buts, BTTS…)
                                                               + Value Bet
                                                               + Bet Builder
```

---

## 1. Sources de données

| Source | Ce qu'elle apporte | Mise à jour |
|---|---|---|
| **football-data.co.uk** | 9 ligues × 15 saisons de matchs historiques (scores, cotes, tirs) | Hebdo via ingestion |
| **ESPN API** | Matchs à venir 7 jours, horaires, blessures | Quotidien |
| **Winamax / Betclic** | Cotes live multi-marchés (1X2, BTTS, Over/Under) | Chaque appel API |
| **Open-Meteo** | Météo du lieu du match | Chaque appel API |
| **RSS / News** | Sentiment des actualités des équipes | Chaque appel API |
| **api-sports.io** | Blessures et suspensions (si clé configurée) | Quotidien |

**9 ligues ingérées** : Premier League, Ligue 1, Bundesliga, La Liga, Serie A, Championship, Eredivisie, Primeira Liga, Süper Lig.

---

## 2. Feature Engineering (31 features)

Toutes calculées **avant** le match (aucune fuite de données).

### A. Probabilités implicites des bookmakers (3)
```
margin = 1/cote_dom + 1/cote_nul + 1/cote_ext
implied_home = (1/cote_dom) / margin   # Prob. victoire domicile épurée du margin
implied_draw = (1/cote_nul) / margin
implied_away = (1/cote_ext) / margin
```
> C'est le signal le plus fort : les bookmakers agrègent l'information du marché.

### B. Elo Ratings (3)
- Calculé en continu sur toute l'histoire depuis 2010
- K=32, initial=1500
- `elo_diff = home_elo - away_elo` → avantage relatif entre les deux équipes

### C. Forme des 5 derniers matchs (6)
- `home_pts_last_5` : moyenne de points (0/1/3) sur 5 matchs
- `home_goals_scored_last_5` / `home_goals_conceded_last_5`
- Idem pour l'équipe extérieure

### D. Forme spécifique terrain (2)
- `home_pts_last_5_at_home` : points uniquement dans les matchs joués à domicile
- `away_pts_last_5_away` : points uniquement en déplacement
> Important car certaines équipes sont très différentes à domicile vs. extérieur.

### E. Tirs cadrés (4)
- `home_sot_last_5` / `away_sot_last_5` : proxy de la dangerosité offensive
- `home_sot_conceded_last_5` / `away_sot_conceded_last_5` : robustesse défensive

### F. xG proxy (2)
- `home_xg_last_5` / `away_xg_last_5` : buts attendus moyens (depuis Understat pour 2014+, imputation par moyenne équipe pour les saisons antérieures)

### G. Fatigue / repos (2)
- `home_days_rest` / `away_days_rest` : jours depuis le dernier match
- Défaut 7.0 pour le premier match de la saison

### H. Momentum et série (4)
- `home_unbeaten_streak` : matchs consécutifs sans défaite
- `away_unbeaten_streak`
- `home_momentum` = pts_last_3 / pts_last_5 (>1 = en hausse, <1 = en baisse)
- `away_momentum`

### I. Confrontations directes H2H (2)
- `h2h_dominance` : (victoires dom - victoires ext) / total matchs H2H
- `h2h_avg_goals` : moyenne de buts par confrontation historique

### J. Interactions engineered (3)
- `form_pts_diff` = home_pts_last_5 − away_pts_last_5
- `goal_diff_home` = buts marqués − buts encaissés (domicile)
- `goal_diff_away` = buts marqués − buts encaissés (extérieur)

---

## 3. Architecture du modèle

Le modèle est un **ensemble à 3 niveaux** (stacking).

### Niveau 1 — NN Ensemble (3 modèles)
```
31 features
    │
    ▼
[Linear(31→128) + BatchNorm + GELU + Dropout(0.3)]   ← Projection
    │
    ▼
[ResidualBlock × 3]   ← skip-connections : x + f(x)
    │
    ▼
[Linear(128→3)]   ← Logits H / D / A
```
- 3 réseaux entraînés avec des seeds différents (13, 42, 99) → les probabilités sont moyennées
- **Temperature scaling** : calibration sur le jeu de validation pour que `proba=0.70` signifie vraiment 70%

### Niveau 1 — XGBoost
- 1000 estimateurs, max_depth=5, learning_rate=0.03
- Early stopping sur la validation (patience=50)
- Poids de classe proportionnel à l'imbalance H/D/A

### Niveau 1 — LightGBM
- 1000 estimateurs, num_leaves=63, learning_rate=0.03
- Plus rapide et souvent légèrement meilleur que XGBoost sur données tabulaires

### Niveau 2 — Méta-learner (Stacking)
```
NN_probs(3) + XGB_probs(3) + LGB_probs(3) + implied_odds(3) = 12 features
    │
    ▼
GradientBoostingClassifier(n_estimators=100, max_depth=3)
    │
    ▼
Probabilités finales H / D / A
```
> Les 3 probabilités implicites passées en entrée permettent au méta-learner de pondérer les modèles selon le contexte marché.

### Sélection du meilleur modèle
À la fin de l'entraînement, les 4 approches sont évaluées sur le jeu de test. La meilleure est sauvegardée dans `best_approach` et utilisée à l'inférence.

---

## 4. Pipeline d'inférence (temps réel)

Quand le frontend appelle `/predictions/upcoming` :

```
1. ESPN API → matchs des 7 prochains jours
2. Bookmakers (Winamax/Betclic) → cotes live
3. DB (MatchFeature) → dernières stats de chaque équipe (31 features)
4. predictor_service.predict(**features)
   → NN ensemble + XGB + LGB + stacking
   → P(Home), P(Draw), P(Away)
5. Ajustements optionnels :
   - Sentiment actualités RSS (+/- 3-5% sur les probas)
   - Blessures api-sports.io (+/- selon sévérité)
6. Recommandation textuelle basée sur les seuils de confiance
7. Value Bet : si P(modèle) > P(bookmaker) + 5%
8. Bet Builder (Poisson) → stats supplémentaires
9. Sauvegarde dans prediction_logs avec features_json
```

---

## 5. Statistiques supplémentaires (Poisson)

La route `/predictions/upcoming` calcule aussi via un **modèle de Poisson** :

| Statistique | Comment calculée |
|---|---|
| **Buts prédits** | Moyenne pondérée des derniers matchs (λ_home, λ_away) |
| **BTTS %** | P(home_goals ≥ 1) × P(away_goals ≥ 1) |
| **Over 2.5 %** | 1 − P(total_goals ≤ 2) via matrice de scores |
| **Over 1.5 %** | 1 − P(total_goals ≤ 1) |
| **Corners** | Moyenne des 10 derniers matchs par équipe |
| **Cartons** | Moyenne des 10 derniers matchs par équipe |

---

## 6. Value Bet

Un **value bet** est détecté quand le modèle pense qu'un résultat est plus probable que ce que le bookmaker propose :

```
edge = P(modèle) − P(bookmaker implicite)
si edge > 5% → Value Bet actif
```

Exemple : modèle dit 55% victoire domicile, bookmaker cote à 1.80 (= 55.6% implicite → pas de value).
Si bookmaker cote à 2.10 (= 47.6% implicite) → edge = 55% − 47.6% = +7.4% → **Value Bet**.

---

## 7. Bet Builder

Génère 3-5 sélections par match combinant les prédictions du modèle et les stats Poisson :

| Clé | Description | Seuil |
|---|---|---|
| `match_result_home` | Victoire domicile | confiance ≥ 60% |
| `match_result_away` | Victoire extérieur | confiance ≥ 60% |
| `double_chance_home` | Domicile ou Nul | confiance ≥ 72% |
| `double_chance_away` | Extérieur ou Nul | confiance ≥ 72% |
| `over_25` | Plus de 2.5 buts | over_pct ≥ 58% |
| `over_15` | Plus de 1.5 buts | over_pct ≥ 72% |
| `btts` | Les deux équipes marquent | btts_pct ≥ 60% |

---

## 8. Feedback loop (amélioration continue)

```
Prédiction sauvegardée (features_json) ──► Match joué ──► /predictions/verify
                                                              │
                                                    Mise à jour is_won dans DB
                                                              │
                                                   (hebdomadaire, lundi 05:00 UTC)
                                                              │
                                                   retrain_with_feedback.py
                                                              │
                                          Méta-learner ré-entraîné sur :
                                          • Val set original (poids 1x)
                                          • Feedbacks récents (poids 3x)
```

- Minimum 30 prédictions vérifiées pour déclencher le retrain
- Seul le **méta-learner** est retouché (rapide, ~quelques secondes)
- NN / XGB / LGB restent fixes jusqu'au re-entraînement complet mensuel

---

## 9. Automatisation

L'automatisation planifiee a ete retiree pendant la phase de developpement.
Les pipelines se lancent manuellement pour garder le projet plus simple tant que le front,
les donnees live et le modele ne sont pas stabilises.

---

## 10. Commandes manuelles

```powershell
# Pipeline complet (première fois ou mise à jour des données)
python -m scripts.migrate_db
python -m src.ingestion.load_historical
python -m src.features.build_features
python -m src.model.train

# Feedback retrain uniquement (si ≥30 prédictions vérifiées)
python -m scripts.retrain_with_feedback

# Vérifier les résultats des prédictions en attente
# → POST /predictions/verify via l'API

# Lancer l'API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 11. Précision attendue

| Approche | Précision test |
|---|---|
| Baseline aléatoire | 33% |
| **Ancien modèle (14 features)** | **~57%** |
| **Nouveau modèle (31 features + LGB + stacking)** | **~62-65% attendu** |
| Plafond théorique (football = aléatoire partiel) | ~68-70% |

> Le plafond de ~70% est difficile à dépasser sans données externes de type blessures/compositions réelles. Les 31 features actuelles capturent l'essentiel de l'information accessible publiquement.
