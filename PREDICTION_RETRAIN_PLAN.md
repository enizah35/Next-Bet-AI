# Plan pour viser 60% d'accuracy globale

Objectif: améliorer le modèle 1/N/2 sur tous les matchs, pas seulement filtrer les pronostics les plus confiants.

Atteindre 60% global en football est ambitieux. La seule façon propre d'y arriver est d'améliorer la donnée, les features, la validation et le training, puis de mesurer sur un vrai test chronologique.

## 1. Charger plus de championnats

La pipeline historique charge maintenant 15 ligues:

- Ligue 1, Premier League, Bundesliga, La Liga, Serie A
- Championship, Ligue 2, 2. Bundesliga, La Liga 2, Serie B
- Eredivisie, Primeira Liga, Super Lig, Belgian Pro League, Scottish Premiership

Les saisons chargées vont de 2010-2011 à 2025-2026 quand les fichiers sont disponibles.

Commande:

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.ingestion.load_historical
```

## 2. Recalculer toutes les features

Toujours reconstruire les features après ingestion.

```powershell
python -m src.features.build_features
```

## 3. Vérifier la base avant training

```powershell
python -m scripts.analyze_data
```

À surveiller:

- nombre total de matchs
- distribution H/D/A
- couverture des cotes `avg_h`, `avg_d`, `avg_a`
- couverture tirs/corners/cartons
- ligues récentes suffisamment représentées

## 4. Features ajoutées pour améliorer le global

Le modèle utilise maintenant des signaux supplémentaires:

- `market_home_away_gap`
- `market_favorite_prob`
- `market_draw_gap`
- `market_entropy`
- `form_goal_diff`
- `xg_diff`
- `sot_diff`
- `sot_conceded_diff`
- `rest_diff`
- `momentum_diff`
- `unbeaten_diff`
- `home_attack_vs_away_defense`
- `away_attack_vs_home_defense`
- `attack_balance`

Ces features améliorent le signal global au lieu de simplement masquer les matchs difficiles.

## 5. Réentraîner le modèle complet

```powershell
python -m src.model.train
```

Le training compare:

- neural network ensemble
- XGBoost
- LightGBM
- stacking

Le meilleur est sauvegardé automatiquement.

## 6. Lire le vrai score global

Fichier:

```text
src/model/checkpoints/training_metrics.json
```

Métrique principale:

```json
"test_accuracy": 0.60
```

Objectif:

```text
test_accuracy >= 0.60
```

Les `confidence_bands` restent un diagnostic de calibration, pas l'objectif principal.

## 7. Si le modèle reste sous 60%

Ordre d'action:

1. Garder seulement les saisons récentes dans une expérience: 2018-2025 ou 2020-2025.
2. Tester un modèle par groupe de ligues: top 5, divisions 2, petites ligues.
3. Ajouter une validation walk-forward par saison.
4. Optimiser les hyperparamètres XGBoost/LightGBM.
5. Renforcer les données de cotes closing, souvent plus prédictives que les stats sportives seules.
6. Ajouter xG réels et compositions seulement si les données sont datées avant match.

## 8. Commande complète

```powershell
.\.venv\Scripts\Activate.ps1
python -m src.ingestion.load_historical
python -m src.features.build_features
python -m scripts.analyze_data
python -m src.model.train
```
