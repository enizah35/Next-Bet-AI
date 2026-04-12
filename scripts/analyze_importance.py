"""Quick analysis of XGBoost feature importance and potential improvements."""
import json
import numpy as np
import xgboost as xgb
from pathlib import Path

MODEL_DIR = Path("src/model/checkpoints")

# Load XGBoost
model = xgb.XGBClassifier()
model.load_model(str(MODEL_DIR / "xgboost_model.json"))

# Feature columns (must match training order)
FEATURE_COLUMNS = [
    "home_pts_last_5", "home_goals_scored_last_5", "home_goals_conceded_last_5",
    "away_pts_last_5", "away_goals_scored_last_5", "away_goals_conceded_last_5",
    "home_elo", "away_elo", "elo_diff",
    "home_pts_last_5_at_home", "away_pts_last_5_away",
    "home_days_rest", "away_days_rest",
    "implied_home", "implied_draw", "implied_away",
    "home_sot_last_5", "away_sot_last_5",
    "home_sot_conceded_last_5", "away_sot_conceded_last_5",
]

importances = model.feature_importances_
sorted_idx = np.argsort(importances)[::-1]

print("XGBoost Feature Importance:")
print("=" * 50)
for i in sorted_idx:
    bar = "#" * int(importances[i] * 100)
    print(f"{FEATURE_COLUMNS[i]:30s} {importances[i]:.4f} {bar}")

# Check training metrics
with open(MODEL_DIR / "training_metrics.json") as f:
    metrics = json.load(f)
print(f"\nBest approach: {metrics.get('best_approach')}")
print(f"All results: {metrics.get('all_results')}")
print(f"Temperature: {metrics.get('temperature')}")
