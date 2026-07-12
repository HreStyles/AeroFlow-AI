"""
Train LightGBM quantile-regression models for delay duration.

One booster per quantile (alpha = 0.1, 0.5, 0.9) — LightGBM's quantile
objective is single-output, so three models are saved:
quantile_p10.txt / quantile_p50.txt / quantile_p90.txt.

Iteration count is selected with a TIME-based holdout (the last training
month, May) — never a random split — then each model is refit on the full
Jan–May window. Delay-duration models train on ALL flights (0 for on-time),
keeping extreme delays in: quantile regression captures exactly the tail
behavior the optimizer needs.
"""
import sys
from pathlib import Path

import lightgbm as lgb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    PROCESSED_DATA_DIR,
    QUANTILE_PATH,
)

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}

BASE_PARAMS = {
    "objective": "quantile",
    "metric": "quantile",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 100,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbosity": -1,
    "seed": 42,
}
MAX_ROUNDS = 2000
EARLY_STOP = 100


def train(train_path: Path | None = None,
          base_out_path: Path | None = None) -> dict[str, lgb.Booster]:
    train_path = train_path or PROCESSED_DATA_DIR / "train.parquet"
    base = Path(base_out_path or QUANTILE_PATH)
    train_df = pd.read_parquet(train_path)

    # Time-based early-stopping holdout: last month of the training window
    last_month = train_df["FlightDate"].dt.to_period("M").max()
    fit_df = train_df[train_df["FlightDate"].dt.to_period("M") < last_month]
    val_df = train_df[train_df["FlightDate"].dt.to_period("M") == last_month]
    print(f"  early-stop holdout: fit {len(fit_df):,} rows, "
          f"validate on {last_month} ({len(val_df):,} rows)")

    boosters = {}
    for name, alpha in QUANTILES.items():
        params = {**BASE_PARAMS, "alpha": alpha}
        dfit = lgb.Dataset(fit_df[FEATURE_NAMES], label=fit_df["label_delay_minutes"],
                           feature_name=FEATURE_NAMES,
                           categorical_feature=CATEGORICAL_FEATURES)
        dval = lgb.Dataset(val_df[FEATURE_NAMES], label=val_df["label_delay_minutes"],
                           reference=dfit)
        probe = lgb.train(
            params, dfit, num_boost_round=MAX_ROUNDS,
            valid_sets=[dval], valid_names=["val"],
            callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
        )
        rounds = probe.best_iteration
        # Refit on the full training window at the selected iteration count
        dtrain = lgb.Dataset(train_df[FEATURE_NAMES],
                             label=train_df["label_delay_minutes"],
                             feature_name=FEATURE_NAMES,
                             categorical_feature=CATEGORICAL_FEATURES)
        booster = lgb.train(params, dtrain, num_boost_round=rounds)

        out = base.with_name(f"{base.stem}_{name}.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        booster.save_model(str(out))
        val_loss = probe.best_score["val"]["quantile"]
        print(f"  alpha={alpha}: {rounds} trees "
              f"(holdout pinball {val_loss:.3f}) → {out}")
        boosters[name] = booster
    return boosters


if __name__ == "__main__":
    train()
