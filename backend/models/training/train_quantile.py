"""
Train LightGBM quantile-regression models for delay duration.

One booster per quantile (alpha = 0.1, 0.5, 0.9) — LightGBM's quantile
objective is single-output, so the three models are saved as
quantile_p10.txt / quantile_p50.txt / quantile_p90.txt (the predictor
resolves them from the base name models/saved/quantile.txt).
"""
import sys
from pathlib import Path

import lightgbm as lgb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import FEATURE_NAMES, PROCESSED_DATA_DIR, QUANTILE_PATH  # noqa: E402

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}

BASE_PARAMS = {
    "objective": "quantile",
    "metric": "quantile",
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "verbosity": -1,
    "seed": 42,
}


def train(train_path: Path | None = None, valid_path: Path | None = None,
          base_out_path: Path | None = None) -> dict[str, lgb.Booster]:
    train_path = train_path or PROCESSED_DATA_DIR / "train.parquet"
    valid_path = valid_path or PROCESSED_DATA_DIR / "test.parquet"
    base = Path(base_out_path or QUANTILE_PATH)

    train_df = pd.read_parquet(train_path)
    valid_df = pd.read_parquet(valid_path)

    # Delay-duration models train on ALL flights (0 for on-time), which keeps
    # extreme delays in — quantile regression captures tail behavior without
    # discarding "outliers" that are exactly the events we care about.
    dtrain = lgb.Dataset(
        train_df[FEATURE_NAMES], label=train_df["label_delay_minutes"],
        feature_name=FEATURE_NAMES,
    )
    dvalid = lgb.Dataset(
        valid_df[FEATURE_NAMES], label=valid_df["label_delay_minutes"],
        reference=dtrain,
    )

    boosters = {}
    for name, alpha in QUANTILES.items():
        print(f"Training quantile model alpha={alpha}…")
        booster = lgb.train(
            {**BASE_PARAMS, "alpha": alpha},
            dtrain,
            num_boost_round=1500,
            valid_sets=[dvalid],
            valid_names=["valid"],
            callbacks=[
                lgb.early_stopping(stopping_rounds=100),
                lgb.log_evaluation(period=200),
            ],
        )
        out = base.with_name(f"{base.stem}_{name}.txt")
        out.parent.mkdir(parents=True, exist_ok=True)
        booster.save_model(str(out))
        print(f"  saved → {out}")
        boosters[name] = booster
    return boosters


if __name__ == "__main__":
    train()
