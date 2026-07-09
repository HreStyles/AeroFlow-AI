"""
FastAPI routes for AeroFlow AI.

The event log returned by /api/presets/{id} and /api/simulate is the single
source of truth for the frontend — playback never calls the backend.
"""
import json

from fastapi import APIRouter, HTTPException

from config import (
    DECISIONS_LOG_PATH,
    MODEL_NOT_TRAINED_MESSAGE,
    PRESETS_DIR,
    VALIDATION_DIR,
)
from component_a.predictor import (
    DelayPredictor,
    HeuristicPredictor,
    ModelNotTrainedError,
    load_predictor,
)
from component_b.airport_models import AirportNotFoundError, load_airport_config
from pipeline.scenario_runner import run_scenario
from .schemas import DecisionRequest, Scenario

router = APIRouter(prefix="/api")


def _resolve_airport(scenario: dict) -> dict:
    """Presets store 'airport' as a code string; expand to the full config."""
    airport = scenario.get("airport")
    if isinstance(airport, str):
        scenario["airport"] = load_airport_config(airport)
    return scenario


@router.get("/health")
def health():
    return {
        "status": "ok",
        "model_trained": DelayPredictor.is_available(),
        "prediction_source": (
            "lightgbm_model" if DelayPredictor.is_available()
            else HeuristicPredictor.PREDICTION_SOURCE
        ),
    }


@router.get("/presets")
def list_presets():
    """List available preset scenarios."""
    presets = []
    if PRESETS_DIR.exists():
        for path in sorted(PRESETS_DIR.glob("*.json")):
            with open(path) as fp:
                data = json.load(fp)
            presets.append({
                "id": data.get("scenario_id", path.stem),
                "name": data.get("scenario_name", path.stem),
                "description": data.get("description", ""),
                "airport": data.get("airport") if isinstance(data.get("airport"), str)
                else data.get("airport", {}).get("airport_code", ""),
                "flight_count": len([
                    f for f in data.get("flights", []) if f.get("status") != "idle"
                ]),
                "gdp_event_count": len(data.get("gdp_events", [])),
            })
    return {"presets": presets}


@router.get("/presets/{preset_id}")
def get_preset(preset_id: str):
    """Run the full pipeline live on a preset scenario and return its event log.

    Presets remain usable before the model is trained: they run with the
    clearly-labeled heuristic fallback predictor in that case.
    """
    scenario_path = PRESETS_DIR / f"{preset_id}.json"
    if not scenario_path.exists():
        raise HTTPException(404, f"Preset '{preset_id}' not found")
    with open(scenario_path) as fp:
        scenario = json.load(fp)

    try:
        scenario = _resolve_airport(scenario)
        predictor = load_predictor(allow_fallback=True)
        return run_scenario(scenario, predictor)
    except AirportNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/simulate")
def simulate_custom(scenario: Scenario):
    """Run the full pipeline on a custom user-submitted scenario.

    Requires trained model files — returns 503 with instructions otherwise
    (custom scenarios never silently use heuristic predictions).
    """
    try:
        predictor = load_predictor(allow_fallback=False)
    except ModelNotTrainedError:
        raise HTTPException(503, MODEL_NOT_TRAINED_MESSAGE)

    scenario_dict = scenario.model_dump()
    try:
        scenario_dict = _resolve_airport(scenario_dict)
        return run_scenario(scenario_dict, predictor)
    except AirportNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))  # completeness-layer rejection


@router.post("/simulate/{scenario_id}/decision")
def record_decision(scenario_id: str, decision: DecisionRequest):
    """Log an operator accept/override decision (the feedback loop)."""
    DECISIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS_LOG_PATH, "a") as fp:
        fp.write(json.dumps({
            "scenario_id": scenario_id,
            "recommendation_id": decision.recommendation_id,
            "selected_rank": decision.selected_rank,
            "decision": decision.decision,
            "override_reason": decision.override_reason,
        }) + "\n")
    return {"logged": True}


@router.get("/airports/{code}")
def get_airport_config(code: str):
    """Return airport layout config (gates, runways, map layout)."""
    try:
        return load_airport_config(code)
    except AirportNotFoundError as e:
        raise HTTPException(404, str(e))


@router.get("/validation/backtest")
def get_backtest_results():
    """Return precomputed historical backtest results (Method 2)."""
    path = VALIDATION_DIR / "backtest_results.json"
    if path.exists():
        with open(path) as fp:
            return json.load(fp)
    return {
        "available": False,
        "message": (
            "Backtest results not yet computed. Train the model "
            "(scripts/train_all.py), then run scripts/generate_presets.py."
        ),
    }
