"""Quick experiment: combo test (depth + feature selection)."""
import numpy as np
import logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
from scripts.experiment_models import load_data, split_data, train_xgb, evaluate, ALL_FEATURES

df = load_data()

# Get top features by importance
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, ALL_FEATURES)
base = train_xgb(X_tr, y_tr, X_v, y_v)
importances = base.feature_importances_
ranked = sorted(zip(ALL_FEATURES, importances), key=lambda x: x[1], reverse=True)
top12 = [f for f, _ in ranked[:12]]
top14 = [f for f, _ in ranked[:14]]
print('Top 12:', top12)
print('Top 14:', top14)

# Test depth=4 + top-12
print('\n=== depth=4 + top-12 ===')
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, top12)
m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=4)
evaluate(m, X_te, y_te, 'XGB d4 top12')

# Test depth=4 + top-14
print('\n=== depth=4 + top-14 ===')
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, top14)
m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=4)
evaluate(m, X_te, y_te, 'XGB d4 top14')

# Test depth=4 + all 20
print('\n=== depth=4 + all 20 ===')
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, ALL_FEATURES)
m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=4)
evaluate(m, X_te, y_te, 'XGB d4 all20')

# Test depth=3 + top-12
print('\n=== depth=3 + top-12 ===')
X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, top12)
m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=3)
evaluate(m, X_te, y_te, 'XGB d3 top12')

# Multi-seed robustness check
print('\n=== Multi-seed robustness check (5 seeds) ===')
for label, feats, depth in [('d4-top12', top12, 4), ('d4-all20', ALL_FEATURES, 4), ('d5-all20', ALL_FEATURES, 5)]:
    accs = []
    for seed in [13, 42, 99, 7, 123]:
        X_tr, y_tr, X_v, y_v, X_te, y_te = split_data(df, feats)
        m = train_xgb(X_tr, y_tr, X_v, y_v, max_depth=depth, random_state=seed)
        preds = m.predict(X_te)
        accs.append(np.mean(preds == y_te))
    print(f'{label}: mean={np.mean(accs):.4f} std={np.std(accs):.4f} [{" ".join(f"{a:.4f}" for a in accs)}]')
