"""
Hyperparameter tuning + fit diagnosis for the delay classifier.

1. Fit diagnosis: train the current config and compare AUC on its own
   training data vs a held-out future month. A large gap ⇒ overfitting;
   both low and close together ⇒ underfitting / feature ceiling.
2. Randomized search over LightGBM hyperparameters, each candidate scored
   with walk-forward (time-ordered) validation folds — never k-fold.
3. Saves the winning config to models/saved/best_params.json, which
   train_classifier.py picks up automatically on the next run.
"""
import json
import random
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import FEATURE_NAMES, MODELS_DIR, PROCESSED_DATA_DIR  # noqa: E402

BEST_PARAMS_PATH = MODELS_DIR / "best_params.json"

BASE = {
    "objective": "binary",
    "metric": "auc",
    "verbosity": -1,
    "seed": 42,
}
CURRENT = {
    **BASE,
    "learning_rate": 0.05, "num_leaves": 63, "min_data_in_leaf": 100,
    "feature_fraction": 0.9, "bagging_fraction": 0.8, "bagging_freq": 5,
}

SEARCH_SPACE = {
    "learning_rate": [0.03, 0.05, 0.08],
    "num_leaves": [31, 63, 127, 255],
    "min_data_in_leaf": [50, 100, 200, 500],
    "max_depth": [-1, 8, 12],
    "feature_fraction": [0.7, 0.85, 1.0],
    "bagging_fraction": [0.7, 0.85, 1.0],
    "lambda_l2": [0.0, 1.0, 10.0],
    "min_gain_to_split": [0.0, 0.1],
}
N_CANDIDATES = 12
MAX_ROUNDS = 3000
EARLY_STOP = 100


def _monthly_folds(df: pd.DataFrame, n_folds: int = 2):
    """Last n_folds walk-forward folds (largest fit windows → most relevant)."""
    months = sorted(df["FlightDate"].dt.to_period("M").unique())
    for val_month in months[-n_folds:]:
        fit = df[df["FlightDate"].dt.to_period("M") < val_month]
        val = df[df["FlightDate"].dt.to_period("M") == val_month]
        yield val_month, fit, val


def _fit_eval(params: dict, fit_df, val_df) -> tuple[float, float, int]:
    dfit = lgb.Dataset(fit_df[FEATURE_NAMES], label=fit_df["label_delayed"])
    dval = lgb.Dataset(val_df[FEATURE_NAMES], label=val_df["label_delayed"],
                       reference=dfit)
    booster = lgb.train(
        params, dfit, num_boost_round=MAX_ROUNDS,
        valid_sets=[dval], valid_names=["val"],
        callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
    )
    val_auc = booster.best_score["val"]["auc"]
    train_auc = roc_auc_score(
        fit_df["label_delayed"],
        booster.predict(fit_df[FEATURE_NAMES], num_iteration=booster.best_iteration),
    )
    return train_auc, val_auc, booster.best_iteration


def main():
    train_df = pd.read_parquet(PROCESSED_DATA_DIR / "train.parquet")
    folds = list(_monthly_folds(train_df, n_folds=2))

    # ── 1. Fit diagnosis on the current config ────────────────────────────────
    print("=" * 64)
    print("FIT DIAGNOSIS (current config)")
    print("=" * 64)
    _, fit_df, val_df = folds[-1]
    train_auc, val_auc, best_iter = _fit_eval(CURRENT, fit_df, val_df)
    gap = train_auc - val_auc
    print(f"  train AUC {train_auc:.4f} | validation AUC {val_auc:.4f} "
          f"| gap {gap:+.4f} | best_iter {best_iter}")
    if gap > 0.05:
        verdict = "OVERFITTING — regularize (fewer leaves, more min_data, L2)"
    elif val_auc < 0.68 and gap < 0.03:
        verdict = ("UNDERFITTING / feature ceiling — more capacity helps little; "
                   "richer features are the real lever")
    else:
        verdict = "reasonable fit — tuning may buy a small improvement"
    print(f"  verdict: {verdict}\n")

    # ── 2. Randomized search with walk-forward validation ────────────────────
    print("=" * 64)
    print(f"RANDOMIZED SEARCH ({N_CANDIDATES} candidates × {len(folds)} folds)")
    print("=" * 64)
    rng = random.Random(7)
    candidates = [CURRENT]
    seen = {json.dumps(CURRENT, sort_keys=True)}
    while len(candidates) < N_CANDIDATES:
        cand = {**BASE, **{k: rng.choice(v) for k, v in SEARCH_SPACE.items()}}
        if cand["bagging_fraction"] < 1.0:
            cand["bagging_freq"] = 5
        key = json.dumps(cand, sort_keys=True)
        if key not in seen:
            seen.add(key)
            candidates.append(cand)

    leaderboard = []
    for i, params in enumerate(candidates):
        val_aucs, train_aucs, iters = [], [], []
        for _, fit_df, val_df in folds:
            tr, va, it = _fit_eval(params, fit_df, val_df)
            train_aucs.append(tr)
            val_aucs.append(va)
            iters.append(it)
        mean_val = float(np.mean(val_aucs))
        leaderboard.append({
            "params": {k: v for k, v in params.items() if k not in BASE},
            "val_auc": round(mean_val, 4),
            "train_auc": round(float(np.mean(train_aucs)), 4),
            "gap": round(float(np.mean(train_aucs)) - mean_val, 4),
            "median_iter": int(np.median(iters)),
        })
        tag = " (current)" if i == 0 else ""
        print(f"  [{i + 1:2d}/{N_CANDIDATES}] val {mean_val:.4f} "
              f"(gap {leaderboard[-1]['gap']:+.4f}){tag} "
              f"{leaderboard[-1]['params']}")

    leaderboard.sort(key=lambda r: r["val_auc"], reverse=True)
    best = leaderboard[0]
    current_score = next(r["val_auc"] for r in leaderboard
                         if r["params"] == leaderboard[0]["params"]
                         or True)  # placeholder replaced below
    current_entry = [r for r in leaderboard
                     if r["params"] == {k: v for k, v in CURRENT.items()
                                        if k not in BASE}][0]

    print("\n" + "=" * 64)
    print("LEADERBOARD (top 5)")
    print("=" * 64)
    for r in leaderboard[:5]:
        print(f"  val {r['val_auc']:.4f} gap {r['gap']:+.4f} {r['params']}")
    improvement = best["val_auc"] - current_entry["val_auc"]
    print(f"\nBest vs current: {best['val_auc']:.4f} vs "
          f"{current_entry['val_auc']:.4f} ({improvement:+.4f})")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with open(BEST_PARAMS_PATH, "w") as fp:
        json.dump({**BASE, **best["params"]}, fp, indent=2)
    print(f"Saved winning config → {BEST_PARAMS_PATH}")
    print("Re-run train_classifier.py to retrain with it.")


if __name__ == "__main__":
    main()
