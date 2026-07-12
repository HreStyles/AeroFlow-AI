"""
Evaluate trained models: AUC-ROC, PR-AUC, calibration curve, pinball loss,
Brier score with Murphy decomposition, log loss, confusion matrices (at
τ=0.5 and at the cost-optimal threshold derived from the cost model), and
reference baselines (logistic regression + route-persistence) that any
claimed GBDT lift must be measured against.

Calibration matters most here: the optimizer makes cost-based decisions using
these probabilities as inputs, so a miscalibrated model corrupts every
downstream recommendation. Saves data/processed/evaluation_report.json.
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    CLASSIFIER_PATH,
    DEFAULT_COST_WEIGHTS,
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


def brier_decomposition(y: np.ndarray, p: np.ndarray, n_bins: int = 10) -> dict:
    """Murphy (1973) decomposition: Brier = reliability − resolution +
    uncertainty. Reliability (lower better) is miscalibration; resolution
    (higher better) is how much the forecasts separate outcomes; uncertainty
    is the base rate's irreducible variance ō(1−ō)."""
    brier = float(np.mean((p - y) ** 2))
    base = float(np.mean(y))
    # Equal-mass bins over the forecast distribution
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    reliability = resolution = 0.0
    n = len(y)
    for k in range(n_bins):
        mask = (p > edges[k]) & (p <= edges[k + 1])
        if not mask.any():
            continue
        p_bar = float(p[mask].mean())
        o_bar = float(y[mask].mean())
        w = mask.sum() / n
        reliability += w * (p_bar - o_bar) ** 2
        resolution += w * (o_bar - base) ** 2
    return {
        "brier_score": round(brier, 5),
        "reliability": round(reliability, 5),
        "resolution": round(resolution, 5),
        "uncertainty": round(base * (1 - base), 5),
        "note": "Brier = reliability − resolution + uncertainty (Murphy 1973); "
                "lower reliability = better calibrated, higher resolution = "
                "more discriminating",
    }


def _confusion_at(y: np.ndarray, proba: np.ndarray, tau: float) -> dict:
    pred = (proba >= tau).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    return {
        "threshold": round(float(tau), 3),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
        "precision": round(tp / max(tp + fp, 1), 4),
        "recall": round(tp / max(tp + fn, 1), 4),
        "fpr": round(fp / max(fp + tn, 1), 4),
        "fnr": round(fn / max(fn + tp, 1), 4),
        "accuracy": round((tp + tn) / len(y), 4),
    }


def cost_optimal_threshold(y: np.ndarray, proba: np.ndarray,
                           miss_cost_per_row: np.ndarray) -> dict:
    """Sweep τ and minimize expected operating cost from the v2 cost model:
    each false positive incurs one representative proactive intervention
    (gate move: gate_conflict_base + 10 min of tow fuel); each false negative
    forfeits that flight's realized delay cost (pax value-of-time + aircraft
    operating cost). The argmin is the threshold an operator should act at —
    NOT 0.5, because the two error costs are asymmetric."""
    w = DEFAULT_COST_WEIGHTS
    intervention_cost = (
        w["gate_conflict_base"] + 10 * w["fuel_taxi_per_minute"]
    )  # $580 representative proactive action
    taus = np.arange(0.02, 0.99, 0.01)
    costs = []
    for tau in taus:
        pred = proba >= tau
        fp_cost = intervention_cost * float((pred & (y == 0)).sum())
        fn_cost = float(miss_cost_per_row[(~pred) & (y == 1)].sum())
        costs.append(fp_cost + fn_cost)
    best = int(np.argmin(costs))
    return {
        "intervention_cost_usd": intervention_cost,
        "mean_missed_disruption_cost_usd": round(
            float(miss_cost_per_row[y == 1].mean()), 2
        ),
        "optimal_tau": round(float(taus[best]), 2),
        "expected_cost_at_optimal_usd": round(costs[best], 2),
        "expected_cost_at_0.5_usd": round(
            costs[int(np.argmin(np.abs(taus - 0.5)))], 2
        ),
    }


def evaluate(test_path: Path | None = None) -> dict:
    test_path = test_path or PROCESSED_DATA_DIR / "test.parquet"
    train_path = PROCESSED_DATA_DIR / "train.parquet"
    test_df = pd.read_parquet(test_path)
    train_df = pd.read_parquet(train_path)
    X = test_df[FEATURE_NAMES]
    y_cls = test_df["label_delayed"].to_numpy()
    y_reg = test_df["label_delay_minutes"].to_numpy()

    report: dict = {"n_test": int(len(test_df)),
                    "positive_rate": round(float(y_cls.mean()), 4)}

    # ── Classifier ────────────────────────────────────────────────────────────
    clf = lgb.Booster(model_file=str(CLASSIFIER_PATH))
    proba = clf.predict(X)
    lgbm_auc = float(roc_auc_score(y_cls, proba))
    report["classifier"] = {
        "auc_roc": round(lgbm_auc, 4),
        "pr_auc": round(float(average_precision_score(y_cls, proba)), 4),
    }

    # ── Reference baselines (any claimed GBDT lift is measured vs these) ─────
    # Median imputation for the LR only: linear models can't route NaN the
    # way LightGBM does. Categorical codes enter as crude numerics — it is a
    # floor, and treating it as such is the point.
    print("Training logistic-regression baseline…")
    logistic = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(max_iter=2000, random_state=42),
    )
    logistic.fit(train_df[FEATURE_NAMES], train_df["label_delayed"])
    logit_proba = logistic.predict_proba(X)[:, 1]
    logit_auc = float(roc_auc_score(y_cls, logit_proba))

    # Persistence: score = the route's train-window mean delay (already an
    # engineered feature, computed train-only) — "predict the historical
    # average" as a ranking rule.
    persistence_auc = float(roc_auc_score(y_cls, test_df["route_avg_delay"]))

    report["baselines"] = {
        "logistic_regression_auc": round(logit_auc, 4),
        "persistence_route_avg_auc": round(persistence_auc, 4),
        "lightgbm_auc": round(lgbm_auc, 4),
        "lift_over_logistic_pts": round((lgbm_auc - logit_auc) * 100, 2),
        "lift_over_persistence_pts": round((lgbm_auc - persistence_auc) * 100, 2),
    }
    print(
        f"  Logistic AUC: {logit_auc:.4f} | Persistence AUC: {persistence_auc:.4f} "
        f"| LightGBM AUC: {lgbm_auc:.4f} | Lift over logistic: "
        f"+{(lgbm_auc - logit_auc) * 100:.2f} pts"
    )

    # ── Proper scores + operating points ─────────────────────────────────────
    report["classifier"]["brier"] = brier_decomposition(y_cls, proba)
    report["classifier"]["log_loss"] = round(float(log_loss(y_cls, proba)), 5)

    # Per-flight missed-disruption cost from the v2 cost model: realized delay
    # minutes × (pax value-of-time + aircraft operating cost). Pax estimated
    # as seating_capacity × 0.84 load factor (same rule as the completeness
    # layer) — BTS rows carry no actual pax counts.
    w = DEFAULT_COST_WEIGHTS
    est_pax = test_df["seating_capacity"].to_numpy() * 0.84
    miss_cost = y_reg * (
        est_pax * w["passenger_delay_per_minute"]
        + w["aircraft_operating_cost_per_minute"]
    )
    report["classifier"]["confusion_at_0.5"] = _confusion_at(y_cls, proba, 0.5)
    tau_info = cost_optimal_threshold(y_cls, proba, miss_cost)
    report["classifier"]["cost_optimal_threshold"] = tau_info
    report["classifier"]["confusion_at_cost_optimal"] = _confusion_at(
        y_cls, proba, tau_info["optimal_tau"]
    )
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

    # ── Monthly degradation: AUC by distance from the training frontier ──────
    monthly = []
    test_df["_month"] = test_df["FlightDate"].dt.to_period("M").astype(str)
    for m, g in test_df.groupby("_month"):
        p = clf.predict(g[FEATURE_NAMES])
        monthly.append({
            "month": m,
            "n": int(len(g)),
            "positive_rate": round(float(g["label_delayed"].mean()), 4),
            "auc": round(float(roc_auc_score(g["label_delayed"], p)), 4),
        })

    # ── Out-of-time 2025: an entire year the model never saw ────────────────
    oot_path = PROCESSED_DATA_DIR / "oot_2025.parquet"
    if oot_path.exists():
        oot_df = pd.read_parquet(oot_path)
        oot_proba = clf.predict(oot_df[FEATURE_NAMES])
        oot_y = oot_df["label_delayed"].to_numpy()
        report["oot_2025"] = {
            "n": int(len(oot_df)),
            "positive_rate": round(float(oot_y.mean()), 4),
            "auc_roc": round(float(roc_auc_score(oot_y, oot_proba)), 4),
            "pr_auc": round(float(average_precision_score(oot_y, oot_proba)), 4),
            "note": "entirely unseen calendar year; aggregates and "
                    "normalizers frozen at the 2024-05 training boundary",
        }
        oot_df["_month"] = oot_df["FlightDate"].dt.to_period("M").astype(str)
        for m, g in oot_df.groupby("_month"):
            p = clf.predict(g[FEATURE_NAMES])
            monthly.append({
                "month": m,
                "n": int(len(g)),
                "positive_rate": round(float(g["label_delayed"].mean()), 4),
                "auc": round(float(roc_auc_score(g["label_delayed"], p)), 4),
            })
        print(f"  UNSEEN-YEAR (2025) AUC: {report['oot_2025']['auc_roc']:.4f} "
              f"on {len(oot_df):,} flights")

    report["monthly_degradation"] = monthly
    print("  monthly AUC (distance from training frontier):")
    for row in monthly:
        print(f"    {row['month']}: AUC {row['auc']:.4f} "
              f"(n={row['n']:,}, base rate {row['positive_rate']:.3f})")

    EVALUATION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVALUATION_REPORT_PATH, "w") as fp:
        json.dump(report, fp, indent=2)
    print(json.dumps(report, indent=2))
    print(f"Saved → {EVALUATION_REPORT_PATH}")
    return report


if __name__ == "__main__":
    evaluate()
