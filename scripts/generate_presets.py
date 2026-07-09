#!/usr/bin/env python
"""
Monte Carlo scenario generation.

Generates a pool of randomized but plausible scenarios per airport into
backend/data/presets/generated/ and prints a disruption-severity summary so
interesting candidates can be hand-picked and promoted to
backend/data/presets/ (results are NOT precomputed — the pipeline runs live
when a preset is requested).

If trained models exist, also runs a quick pipeline stress pass over a sample
of generated scenarios and writes an aggregate report to
backend/data/validation/backtest_results.json.

Usage:
    backend/.venv/bin/python scripts/generate_presets.py [N_PER_AIRPORT]
"""
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from config import PRESETS_DIR, SUPPORTED_AIRPORTS, VALIDATION_DIR  # noqa: E402
from component_a.predictor import DelayPredictor, load_predictor  # noqa: E402
from component_b.airport_models import load_airport_config  # noqa: E402
from generators.scenario_generator import generate_pool  # noqa: E402
from pipeline.scenario_runner import run_scenario  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    out_dir = PRESETS_DIR / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_scenarios = []
    for airport in SUPPORTED_AIRPORTS:
        config = load_airport_config(airport)
        pool = generate_pool(config, n=n)
        for scenario in pool:
            path = out_dir / f"{scenario['scenario_id']}.json"
            with open(path, "w") as fp:
                json.dump(scenario, fp, indent=2)
        all_scenarios.extend(pool)
        n_disrupted = sum(
            1 for s in pool
            if any(f.get("injected_delay_cause") for f in s["flights"])
        )
        print(f"{airport}: wrote {len(pool)} scenarios "
              f"({n_disrupted} with injected disruptions) → {out_dir}")

    # Stress pass: only when a real trained model exists (heuristic-fallback
    # stress numbers would be misleading as "backtest" results).
    if not DelayPredictor.is_available():
        print("\nModel not trained — skipping pipeline stress pass / backtest "
              "report. Run scripts/train_all.py first for that step.")
        return

    print("\nRunning pipeline stress pass on a sample…")
    predictor = load_predictor(allow_fallback=False)
    sample = all_scenarios[:: max(1, len(all_scenarios) // 20)]
    results = []
    for scenario in sample:
        resolved = {**scenario, "airport": load_airport_config(scenario["airport"])}
        try:
            log = run_scenario(resolved, predictor)
            v = log["validation"]
            results.append({
                "scenario_id": scenario["scenario_id"],
                "n_events": len(log["events"]),
                "baseline_costs": v["baseline_costs"],
                "optimality_gap_pct": v["optimality_gap_pct"],
                "stable_pct": v["sensitivity"]["stable_pct"],
            })
        except Exception as e:  # a failing generated scenario is a finding
            results.append({"scenario_id": scenario["scenario_id"], "error": str(e)})

    ok = [r for r in results if "error" not in r]
    savings = [
        1 - r["baseline_costs"]["milp"] / r["baseline_costs"]["do_nothing"]
        for r in ok if r["baseline_costs"]["do_nothing"] > 0
    ]
    report = {
        "available": True,
        "type": "monte_carlo_stress",
        "n_scenarios": len(results),
        "n_failed": len(results) - len(ok),
        "avg_cost_reduction_vs_do_nothing_pct": round(
            100 * sum(savings) / len(savings), 1
        ) if savings else 0.0,
        "avg_stability_pct": round(
            sum(r["stable_pct"] for r in ok) / len(ok), 1
        ) if ok else 0.0,
        "results": results,
    }
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    out = VALIDATION_DIR / "backtest_results.json"
    with open(out, "w") as fp:
        json.dump(report, fp, indent=2)
    print(f"Stress report ({len(ok)}/{len(results)} scenarios OK) → {out}")


if __name__ == "__main__":
    main()
