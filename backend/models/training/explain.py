"""
Global SHAP feature importance for the trained classifier.

Saves models/saved/shap_global.json with mean |SHAP| per feature — used to
verify the model learned sensible physics (weather severity should rank near
the top) and displayed on the Validation page.
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import shap

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    CLASSIFIER_PATH,
    FEATURE_NAMES,
    PROCESSED_DATA_DIR,
    SHAP_GLOBAL_PATH,
)


def explain(test_path: Path | None = None, sample_size: int = 5000) -> dict:
    test_path = test_path or PROCESSED_DATA_DIR / "test.parquet"
    test_df = pd.read_parquet(test_path)
    if len(test_df) > sample_size:
        test_df = test_df.sample(sample_size, random_state=42)
    X = test_df[FEATURE_NAMES]

    clf = lgb.Booster(model_file=str(CLASSIFIER_PATH))
    explainer = shap.TreeExplainer(clf)
    # Binary classifiers may return per-class values as (2, n, features) or
    # (n, features, 2) depending on the shap version — take the positive class.
    shap_values = np.asarray(explainer.shap_values(X))
    if shap_values.ndim == 3:
        if shap_values.shape[0] == 2 and shap_values.shape[-1] == len(FEATURE_NAMES):
            shap_values = shap_values[-1]
        else:
            shap_values = shap_values[..., -1]

    mean_abs = np.abs(shap_values).mean(axis=0)
    importance = sorted(
        [
            {"feature": name, "mean_abs_shap": round(float(v), 4)}
            for name, v in zip(FEATURE_NAMES, mean_abs)
        ],
        key=lambda x: x["mean_abs_shap"],
        reverse=True,
    )

    result = {"sample_size": int(len(X)), "global_importance": importance}
    SHAP_GLOBAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SHAP_GLOBAL_PATH, "w") as fp:
        json.dump(result, fp, indent=2)
    print(json.dumps(importance[:8], indent=2))
    print(f"Saved → {SHAP_GLOBAL_PATH}")
    return result


if __name__ == "__main__":
    explain()
