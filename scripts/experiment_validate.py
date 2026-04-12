"""Multi-seed validation for top-14 feature config."""
import numpy as np
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
from scripts.experiment_models import load_data, split_data, train_xgb, ALL_FEATURES

df = load_data()

# Get top features
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, ALL_FEATURES)
base = train_xgb(X_tr, y_tr, X_v, y_v)
ranked = sorted(zip(ALL_FEATURES, base.feature_importances_), key=lambda x: x[1], reverse=True)

for top_n in [12, 13, 14, 15, 16]:
    feats = [f for f, _ in ranked[:top_n]]
    for depth in [3, 4, 5]:
        accs = []
        for seed in [13, 42, 99, 7, 123, 256, 314, 512, 1024, 2048]:
            X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, feats)
            m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=depth, random_state=seed)
            preds = m.predict(X_te)
            accs.append(np.mean(preds == y_te))
        print(f'd{depth}-top{top_n}: mean={np.mean(accs):.4f} std={np.std(accs):.4f} best={max(accs):.4f} worst={min(accs):.4f}')
    print()

# Also test top-14 with LightGBM
import lightgbm as lgb
print("=== LightGBM comparison (10 seeds) ===")
top14 = [f for f, _ in ranked[:14]]
for depth in [3, 4, 5]:
    accs = []
    for seed in [13, 42, 99, 7, 123, 256, 314, 512, 1024, 2048]:
        X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, top14)
        from scripts.experiment_models import train_lgb
        m = train_lgb(X_tr, y_tr, X_v, y_v, max_depth=depth, random_state=seed)
        preds = m.predict(X_te)
        accs.append(np.mean(preds == y_te))
    print(f'LGB d{depth}-top14: mean={np.mean(accs):.4f} std={np.std(accs):.4f} best={max(accs):.4f}')
