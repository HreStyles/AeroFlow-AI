"""
Train the LightGBM binary classifier for P(arrival delay > 15 min).
Saves the booster to models/saved/classifier.txt.
"""
import sys
from pathlib import Path

import lightgbm as lgb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import CLASSIFIER_PATH, FEATURE_NAMES, PROCESSED_DATA_DIR  # noqa: E402

PARAMS = {
    "objective": "binary",
    "metric": ["auc", "binary_logloss"],
    "learning_rate": 0.05,
    "num_leaves": 63,
    "min_data_in_leaf": 50,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    # Class imbalance: most flights are on time — reweight the minority class
    "is_unbalance": True,
    "verbosity": -1,
    "seed": 42,
}


def train(train_path: Path | None = None, valid_path: Path | None = None,
          out_path: Path | None = None) -> lgb.Booster:
    train_path = train_path or PROCESSED_DATA_DIR / "train.parquet"
    valid_path = valid_path or PROCESSED_DATA_DIR / "test.parquet"
    out_path = Path(out_path or CLASSIFIER_PATH)

    train_df = pd.read_parquet(train_path)
    valid_df = pd.read_parquet(valid_path)

    dtrain = lgb.Dataset(
        train_df[FEATURE_NAMES], label=train_df["label_delayed"],
        feature_name=FEATURE_NAMES,
    )
    dvalid = lgb.Dataset(
        valid_df[FEATURE_NAMES], label=valid_df["label_delayed"],
        reference=dtrain,
    )

    booster = lgb.train(
        PARAMS,
        dtrain,
        num_boost_round=2000,
        valid_sets=[dvalid],
        valid_names=["valid"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=100),
        ],
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(out_path))
    print(f"Saved classifier ({booster.best_iteration} trees) → {out_path}")
    return booster


if __name__ == "__main__":
    train()
