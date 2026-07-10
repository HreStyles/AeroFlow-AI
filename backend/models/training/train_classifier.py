"""
Train the LightGBM binary classifier for P(arrival delay > 15 min).

Model selection uses TIME-SERIES cross-validation (walk-forward on calendar
months), never k-fold — random folds would train on future flights and
validate on past ones, leaking temporal information. The final model is
refit on the full Jan–May training window at the CV-selected iteration
count and saved to models/saved/classifier.txt.
"""
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import CLASSIFIER_PATH, FEATURE_NAMES, PROCESSED_DATA_DIR  # noqa: E402

PARAMS = {
    "objective": "binary",
    # AUC only: adding logloss would drive early stopping, and no class
    # reweighting (is_unbalance/scale_pos_weight) — reweighting inflates
    # predicted probabilities, and the MILP optimizer consumes these
    # probabilities as calibrated inputs. The ~18% positive rate is mild
    # enough to learn directly; PR-AUC is monitored in evaluate.py.
    "metric": "auc",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbosity": -1,
    "seed": 42,
}
MAX_ROUNDS = 3000
EARLY_STOP = 100

# tune.py saves its winning config here; use it when present
_BEST_PARAMS = Path(__file__).resolve().parents[1] / "saved" / "best_params.json"
if _BEST_PARAMS.exists():
    import json as _json
    with open(_BEST_PARAMS) as _fp:
        PARAMS = {**_json.load(_fp), "verbosity": -1, "seed": 42}
    print(f"Using tuned hyperparameters from {_BEST_PARAMS}")


def _walk_forward_folds(train_df: pd.DataFrame):
    """Expanding-window monthly folds: train ≤ month m, validate on m+1."""
    months = sorted(train_df["FlightDate"].dt.to_period("M").unique())
    for i in range(1, len(months)):
        fit_idx = train_df["FlightDate"].dt.to_period("M") <= months[i - 1]
        val_idx = train_df["FlightDate"].dt.to_period("M") == months[i]
        yield months[i], train_df[fit_idx], train_df[val_idx]


def train(train_path: Path | None = None, out_path: Path | None = None) -> lgb.Booster:
    train_path = train_path or PROCESSED_DATA_DIR / "train.parquet"
    out_path = Path(out_path or CLASSIFIER_PATH)
    train_df = pd.read_parquet(train_path)

    # ── Time-series CV (walk-forward) for iteration count + honest AUC ──────
    best_iters, fold_aucs = [], []
    for val_month, fit_df, val_df in _walk_forward_folds(train_df):
        dfit = lgb.Dataset(fit_df[FEATURE_NAMES], label=fit_df["label_delayed"],
                           feature_name=FEATURE_NAMES)
        dval = lgb.Dataset(val_df[FEATURE_NAMES], label=val_df["label_delayed"],
                           reference=dfit)
        booster = lgb.train(
            PARAMS, dfit, num_boost_round=MAX_ROUNDS,
            valid_sets=[dval], valid_names=["val"],
            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
        )
        auc = booster.best_score["val"]["auc"]
        best_iters.append(booster.best_iteration)
        fold_aucs.append(auc)
        print(f"  fold → validate {val_month}: AUC {auc:.4f} "
              f"(fit {len(fit_df):,} rows, best_iter {booster.best_iteration})")
    print(f"  walk-forward CV AUC: {np.mean(fold_aucs):.4f} "
          f"± {np.std(fold_aucs):.4f}")

    # ── Final fit on the full training window ───────────────────────────────
    final_rounds = int(np.median(best_iters))
    dtrain = lgb.Dataset(train_df[FEATURE_NAMES], label=train_df["label_delayed"],
                         feature_name=FEATURE_NAMES)
    booster = lgb.train(PARAMS, dtrain, num_boost_round=final_rounds)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_path))
    print(f"Saved classifier ({final_rounds} trees, "
          f"{len(train_df):,} training rows) → {out_path}")
    return booster


if __name__ == "__main__":
    train()
