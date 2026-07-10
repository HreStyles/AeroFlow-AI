"""
Evaluate trained models: AUC-ROC, PR-AUC, calibration curve, pinball loss.

Calibration matters most here: the optimizer makes cost-based decisions using
these probabilities as inputs, so a miscalibrated model corrupts every
downstream recommendation. Saves models/saved/evaluation_report.json.
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    CLASSIFIER_PATH,
    EVALUATION_REPORT_PATH,
    FEATURE_NAMES,
    PROCESSED_DATA_DIR,
    QUANTILE_PATH,
)

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}


def pinball_loss(y_true: np.ndarray, y_pred: np.ndarray, alpha: float) -> float:
    """Quantile (pinball) loss — measures calibration of the predicted
    distribution, not just the point estimate."""
    diff = y_true - y_pred
    return float(np.mean(np.maximum(alpha * diff, (alpha - 1) * diff)))


def evaluate(test_path: Path | None = None) -> dict:
    test_path = test_path or PROCESSED_DATA_DIR / "test.parquet"
    test_df = pd.read_parquet(test_path)
    X = test_df[FEATURE_NAMES]
    y_cls = test_df["label_delayed"].to_numpy()
    y_reg = test_df["label_delay_minutes"].to_numpy()

    report: dict = {"n_test": int(len(test_df)),
                    "positive_rate": round(float(y_cls.mean()), 4)}

    # ── Classifier ────────────────────────────────────────────────────────────
    clf = lgb.Booster(model_file=str(CLASSIFIER_PATH))
    proba = clf.predict(X)
    report["classifier"] = {
        "auc_roc": round(float(roc_auc_score(y_cls, proba)), 4),
        "pr_auc": round(float(average_precision_score(y_cls, proba)), 4),
    }
    frac_pos, mean_pred = calibration_curve(y_cls, proba, n_bins=10, strategy="quantile")
    report["classifier"]["calibration_curve"] = [
        {"mean_predicted": round(float(mp), 4), "fraction_positive": round(float(fp), 4)}
        for mp, fp in zip(mean_pred, frac_pos)
    ]
    report["classifier"]["calibration_error"] = round(
        float(np.mean(np.abs(frac_pos - mean_pred))), 4
    )

    # ── Quantile models ───────────────────────────────────────────────────────
    base = Path(QUANTILE_PATH)
    report["quantile"] = {}
    preds = {}
    for name, alpha in QUANTILES.items():
        booster = lgb.Booster(
            model_file=str(base.with_name(f"{base.stem}_{name}.txt"))
        )
        pred = booster.predict(X)
        preds[name] = pred
        report["quantile"][name] = {
            "alpha": alpha,
            "pinball_loss": round(pinball_loss(y_reg, pred, alpha), 4),
            # Empirical coverage: share of true values below the predicted
            # quantile — should be ≈ alpha for a calibrated model
            "empirical_coverage": round(float(np.mean(y_reg <= pred)), 4),
        }
    # Point-prediction accuracy using the median (P50) as the point estimate
    report["quantile"]["point_prediction"] = {
        "mae_minutes": round(float(np.mean(np.abs(y_reg - preds["p50"]))), 2),
        "rmse_minutes": round(float(np.sqrt(np.mean((y_reg - preds["p50"]) ** 2))), 2),
    }
    report["quantile"]["interval_80_coverage"] = round(
        float(np.mean((y_reg >= preds["p10"]) & (y_reg <= preds["p90"]))), 4
    )

    EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVALUATION_REPORT_PATH, "w") as fp:
        json.dump(report, fp, indent=2)
    print(json.dumps(report, indent=2))
    print(f"Saved → {EVALUATION_REPORT_PATH}")
    return report


if __name__ == "__main__":
    evaluate()
