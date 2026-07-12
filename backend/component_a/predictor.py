"""
Component A — the ML prediction layer.

DelayPredictor loads trained LightGBM models from backend/models/saved/ and
runs inference: delay probability, P10/P50/P90 delay-duration quantiles, a
confidence score derived from distribution width, and top-5 SHAP attributions.

There is NO mock predictor. If model files are missing:
  * load_predictor() raises ModelNotTrainedError — the /api/simulate route
    surfaces this as a 503 telling the user to run the training pipeline.
  * Preset scenarios may explicitly opt into HeuristicPredictor, a clearly
    labeled development fallback (every output is tagged with
    prediction_source = "heuristic_fallback (model not trained)").
"""
import json
from pathlib import Path

import numpy as np

from config import (
    CLASSIFIER_PATH,
    CONFIDENCE_SPREAD_NORM_MINUTES,
    CONGESTION_MAP,
    FEATURE_NAMES,
    LOOKUPS_PATH,
    MODEL_NOT_TRAINED_MESSAGE,
    QUANTILE_PATH,
)
from .feature_engineering import build_feature_vector, compute_schedule_slack


class ModelNotTrainedError(RuntimeError):
    """Raised when prediction is attempted but no trained model exists."""

    def __init__(self, message: str = MODEL_NOT_TRAINED_MESSAGE):
        super().__init__(message)


def _quantile_paths(quantile_path: str | Path) -> dict[str, Path]:
    """LightGBM trains one booster per quantile objective, so 'quantile.txt'
    is a base name resolving to quantile_p10.txt / _p50.txt / _p90.txt."""
    base = Path(quantile_path)
    stem = base.stem  # "quantile"
    return {
        "p10": base.with_name(f"{stem}_p10.txt"),
        "p50": base.with_name(f"{stem}_p50.txt"),
        "p90": base.with_name(f"{stem}_p90.txt"),
    }


class DelayPredictor:
    """Real predictor backed by trained LightGBM model files."""

    def __init__(self, classifier_path: str | Path = CLASSIFIER_PATH,
                 quantile_path: str | Path = QUANTILE_PATH):
        import lightgbm as lgb
        import shap

        classifier_path = Path(classifier_path)
        qpaths = _quantile_paths(quantile_path)
        missing = [p for p in [classifier_path, *qpaths.values()] if not p.exists()]
        if missing:
            raise ModelNotTrainedError()

        self.classifier = lgb.Booster(model_file=str(classifier_path))
        self.quantile_models = {
            q: lgb.Booster(model_file=str(p)) for q, p in qpaths.items()
        }
        self.explainer = shap.TreeExplainer(self.classifier)
        self.feature_names = FEATURE_NAMES

        # Historical lookups produced by the training pipeline (route averages,
        # carrier OTP, aircraft ages). Optional — documented defaults apply.
        self.lookups: dict = {}
        if Path(LOOKUPS_PATH).exists():
            with open(LOOKUPS_PATH) as fp:
                self.lookups = json.load(fp)

    @staticmethod
    def is_available(classifier_path: str | Path = CLASSIFIER_PATH,
                     quantile_path: str | Path = QUANTILE_PATH) -> bool:
        qpaths = _quantile_paths(quantile_path)
        return Path(classifier_path).exists() and all(p.exists() for p in qpaths.values())

    def predict(self, flight: dict, scenario_context: dict) -> dict:
        """Run inference for one flight given the scenario context."""
        context = dict(scenario_context)
        for key in ("route_averages", "carrier_stats", "aircraft_registry",
                    "categorical_levels"):
            context.setdefault(key, self.lookups.get(key, {}))

        features = build_feature_vector(flight, context, self.feature_names)
        feature_array = np.array([features], dtype=float)

        # Classification: P(delay > 15 min)
        probability = float(self.classifier.predict(feature_array)[0])

        # Quantile regression: P10 / P50 / P90 of delay minutes
        p10 = float(self.quantile_models["p10"].predict(feature_array)[0])
        p50 = float(self.quantile_models["p50"].predict(feature_array)[0])
        p90 = float(self.quantile_models["p90"].predict(feature_array)[0])
        # Enforce monotonicity (independently trained quantiles can cross)
        p10, p50, p90 = sorted([p10, p50, p90])

        # Confidence: narrow predicted distribution ⇒ high confidence
        spread = p90 - p10
        confidence = max(0.0, min(1.0, 1.0 - spread / CONFIDENCE_SPREAD_NORM_MINUTES))

        # SHAP: local explanation for this prediction. Binary classifiers may
        # return per-class values as (2, n, features) or (n, features, 2)
        # depending on the shap version — always take the positive class.
        shap_values = np.asarray(self.explainer.shap_values(feature_array))
        n_features = len(self.feature_names)
        if shap_values.ndim == 3:
            if shap_values.shape[0] == 2 and shap_values.shape[-1] == n_features:
                shap_values = shap_values[-1]
            else:
                shap_values = shap_values[..., -1]
        row = shap_values[0]
        shap_factors = sorted(
            [
                {"feature": name, "contribution": round(float(val), 3)}
                for name, val in zip(self.feature_names, row)
            ],
            key=lambda x: abs(x["contribution"]),
            reverse=True,
        )[:5]

        return {
            "probability": round(probability, 3),
            "p10_minutes": round(max(0.0, p10), 1),
            "p50_minutes": round(max(0.0, p50), 1),
            "p90_minutes": round(max(0.0, p90), 1),
            "confidence": round(confidence, 3),
            "shap_factors": shap_factors,
            "prediction_source": "lightgbm_model",
        }


class HeuristicPredictor:
    """Development fallback used ONLY for preset scenarios when no trained
    model exists. Deterministic, physically-motivated heuristics; identical
    output schema to DelayPredictor; every result is clearly labeled."""

    PREDICTION_SOURCE = "heuristic_fallback (model not trained)"

    def predict(self, flight: dict, scenario_context: dict) -> dict:
        origin_wx = flight["origin_weather_severity"]
        dest_wx = flight["destination_weather_severity"]
        origin_cg = CONGESTION_MAP[flight["origin_congestion"]]
        dest_cg = CONGESTION_MAP[flight["destination_congestion"]]
        slack = compute_schedule_slack(flight, scenario_context)

        # Weather at either end + congestion drive delay probability; thin
        # rotation slack amplifies it.
        wx = max(origin_wx, dest_wx * 0.8)
        cg = max(origin_cg, dest_cg * 0.7)
        slack_factor = max(0.0, min(0.25, (20.0 - slack) / 80.0))
        probability = min(0.95, 0.08 + wx * 0.55 + cg * 0.25 + slack_factor)

        p50 = probability * 65.0
        p10 = p50 * 0.4
        p90 = p50 * 2.1
        spread = p90 - p10
        confidence = max(0.3, min(1.0, 1.0 - spread / CONFIDENCE_SPREAD_NORM_MINUTES))

        factors = [
            {"feature": "origin_weather_severity", "contribution": round(origin_wx * 0.45, 3)},
            {"feature": "dest_weather_severity", "contribution": round(dest_wx * 0.30, 3)},
            {"feature": "origin_congestion_numeric", "contribution": round(origin_cg * 0.25, 3)},
            {"feature": "dest_congestion_numeric", "contribution": round(dest_cg * 0.15, 3)},
            {"feature": "schedule_slack_minutes", "contribution": round(-slack / 400.0, 3)},
        ]
        factors.sort(key=lambda f: abs(f["contribution"]), reverse=True)

        return {
            "probability": round(probability, 3),
            "p10_minutes": round(max(0.0, p10), 1),
            "p50_minutes": round(max(0.0, p50), 1),
            "p90_minutes": round(max(0.0, p90), 1),
            "confidence": round(confidence, 3),
            "shap_factors": factors[:5],
            "prediction_source": self.PREDICTION_SOURCE,
        }


def load_predictor(allow_fallback: bool = False):
    """Factory used by API routes.

    allow_fallback=False (custom /api/simulate): raises ModelNotTrainedError
    when models are missing, so the route can return a clear 503.
    allow_fallback=True (presets): returns HeuristicPredictor instead.
    """
    if DelayPredictor.is_available():
        return DelayPredictor()
    if allow_fallback:
        return HeuristicPredictor()
    raise ModelNotTrainedError()
