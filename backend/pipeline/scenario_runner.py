"""
Full A → B → C pipeline for one scenario.

Input:  scenario dict (airport already resolved to a full config dict) +
        an injected predictor (DelayPredictor or HeuristicPredictor — the
        API routes decide which; this module never falls back silently).
Output: EventLog dict (timestamped events for frontend playback) including
        ValidationResults (optimality gap, 4-strategy baseline comparison,
        cost-weight sensitivity).
"""
from datetime import datetime, timedelta

from config import (
    CASCADE_COST_THRESHOLD,
    DEFAULT_COST_WEIGHTS,
    DELAY_PROBABILITY_THRESHOLD,
    MIN_MEANINGFUL_DELAY_MINUTES,
)
from component_b.simulation_engine import SimulationEngine
from component_c.baselines import run_baselines
from component_c.optimizer import MILPOptimizer
from .completeness_layer import provenance_summary, validate_and_complete
from .event_log import EventLogBuilder


def _offset_time(time_str: str, offset_minutes: int) -> str:
    t = datetime.strptime(time_str[:5], "%H:%M") + timedelta(minutes=offset_minutes)
    return t.strftime("%H:%M")


def run_scenario(scenario: dict, predictor) -> dict:
    """Execute the full pipeline and return an EventLog dict."""
    airport_config = scenario["airport"]
    if isinstance(airport_config, str):
        raise ValueError(
            "scenario['airport'] must be a resolved airport config dict; "
            "resolve the code via component_b.airport_models.load_airport_config first."
        )

    cost_weights = {**DEFAULT_COST_WEIGHTS, **(scenario.get("cost_weights") or {})}
    day_of_week, month = _scenario_calendar(scenario)

    sim_engine = SimulationEngine(airport_config, cost_weights)
    optimizer = MILPOptimizer(cost_weights)
    log = EventLogBuilder(
        scenario["scenario_id"],
        scenario.get("scenario_name", ""),
        airport_config.get("airport_code", ""),
    )

    # ── Step 1: completeness layer — validate/derive/assume every flight ─────
    flights_dict: dict[str, dict] = {}
    provenance_all: dict[str, dict] = {}
    for flight in scenario["flights"]:
        completed, provenance = validate_and_complete(flight, airport_config)
        flights_dict[completed["flight_id"]] = completed
        provenance_all[completed["flight_id"]] = provenance

    # ── Step 2: build the operational dependency graph ────────────────────────
    sim_engine.build_operational_graph(list(flights_dict.values()))

    # ── Step 3: GDP events ────────────────────────────────────────────────────
    for gdp in scenario.get("gdp_events", []):
        log.add_event(gdp["start_time"], "gdp_started", None, dict(gdp))
        log.add_event(gdp["end_time"], "gdp_ended", None, dict(gdp))

    # ── Step 4: process flights chronologically ───────────────────────────────
    prediction_source = ""
    cascades_for_validation: list[dict] = []
    gap_samples: list[float] = []
    rec_counter = 0

    sorted_flights = sorted(
        flights_dict.values(), key=lambda f: f["scheduled_departure"]
    )
    context = {
        "flights": list(flights_dict.values()),
        "airport_config": airport_config,
        "day_of_week": day_of_week,
        "month": month,
    }

    for flight in sorted_flights:
        fid = flight["flight_id"]
        is_spare = flight.get("status") == "idle"

        if not is_spare:
            log.add_event(flight["scheduled_departure"], "flight_departure", fid, {
                "flight_id": fid,
                "origin": flight["origin"],
                "destination": flight["destination"],
                "gate": flight["assigned_gate"],
                "tail_number": flight["tail_number"],
                "aircraft_type": flight["aircraft_type"],
            })

        # Disruption injection (testing controls)
        injected_minutes = 0
        if flight.get("injected_delay_cause"):
            injected_minutes = flight.get("injected_delay_minutes") or 30
            inject_time = flight.get("injected_delay_time") or flight["scheduled_departure"]
            log.add_event(inject_time, "disruption_injected", fid, {
                "cause": flight["injected_delay_cause"],
                "delay_minutes": injected_minutes,
            })

        if is_spare:
            continue  # spares don't fly; they exist for swap actions

        # ── Component A: predict ──────────────────────────────────────────────
        prediction = predictor.predict(flight, context)
        prediction_source = prediction.get("prediction_source", prediction_source)
        prediction = {
            **prediction,
            "flight_id": fid,
            "provenance": provenance_all.get(fid, {}),
        }

        if prediction["probability"] > DELAY_PROBABILITY_THRESHOLD or injected_minutes:
            pred_time = _offset_time(flight["scheduled_departure"], -15)
            log.add_event(pred_time, "delay_predicted", fid, prediction)

            # ── Component B: simulate the cascade using the P50 delay ─────────
            delay_minutes = max(prediction["p50_minutes"], injected_minutes)
            if delay_minutes > MIN_MEANINGFUL_DELAY_MINUTES:
                cascade = sim_engine.propagate_delay(fid, delay_minutes, flights_dict)

                if cascade["baseline_cost"] > CASCADE_COST_THRESHOLD:
                    cascade_time = _offset_time(flight["scheduled_departure"], -12)
                    log.add_event(cascade_time, "cascade_detected", fid, cascade)
                    cascades_for_validation.append(cascade)

                    # ── Component C: optimize the response ────────────────────
                    recommendation = optimizer.optimize(
                        cascade, flights_dict, airport_config, sim_engine
                    )
                    if recommendation.get("optimality_gap_pct") is not None:
                        gap_samples.append(recommendation["optimality_gap_pct"])
                    rec_counter += 1
                    rec_time = _offset_time(flight["scheduled_departure"], -10)
                    log.add_event(rec_time, "recommendation_generated", fid, {
                        "recommendation_id": f"rec_{rec_counter:03d}_{fid}",
                        "trigger_flight": fid,
                        "ranked_options": recommendation["ranked_options"],
                        "optimality_gap_pct": recommendation["optimality_gap_pct"],
                        "solver_time_seconds": recommendation["solver_time_seconds"],
                        "solver_status": recommendation.get("solver_status", ""),
                    })

        log.add_event(flight["scheduled_arrival"], "flight_arrival", fid, {
            "flight_id": fid,
            "gate": flight["assigned_gate"],
            "origin": flight["origin"],
            "destination": flight["destination"],
        })

    # ── Step 5: validation results (Methods 1, 3, 4) ──────────────────────────
    validation = _compute_validation(
        cascades_for_validation, flights_dict, airport_config,
        sim_engine, cost_weights, gap_samples,
    )
    validation["provenance_summary"] = provenance_summary(provenance_all)

    return log.build(
        validation,
        flights=list(flights_dict.values()),
        provenance=provenance_all,
        prediction_source=prediction_source,
    )


def _scenario_calendar(scenario: dict) -> tuple[int, int]:
    """day_of_week (0=Mon) and month from the first flight's date."""
    try:
        date = datetime.strptime(scenario["flights"][0]["flight_date"], "%Y-%m-%d")
        return date.weekday(), date.month
    except (KeyError, IndexError, ValueError):
        from config import DEFAULT_DAY_OF_WEEK, DEFAULT_MONTH
        return DEFAULT_DAY_OF_WEEK, DEFAULT_MONTH


def _compute_validation(cascades: list[dict], flights_dict: dict,
                        airport_config: dict, sim_engine,
                        cost_weights: dict, gap_samples: list[float]) -> dict:
    """Method 1 (optimality gap), Method 3 (baseline comparison),
    Method 4 (cost-weight sensitivity) — computed on the scenario's largest
    cascade, all from real solver/simulation runs."""
    if not cascades:
        return {
            "optimality_gap_pct": 0.0,
            "baseline_costs": {"do_nothing": 0.0, "random": 0.0,
                               "greedy": 0.0, "milp": 0.0},
            "sensitivity": {"stable_pct": 100, "fragile_ranges": [],
                            "note": "No cascade exceeded the cost threshold."},
        }

    main_cascade = max(cascades, key=lambda c: c["baseline_cost"])

    # Method 3: 4-strategy comparison, summed across every detected cascade
    baseline_costs = {"do_nothing": 0.0, "random": 0.0, "greedy": 0.0, "milp": 0.0}
    for cascade in cascades:
        per_cascade = run_baselines(
            cascade, flights_dict, airport_config, sim_engine, cost_weights
        )
        for strategy, cost in per_cascade.items():
            baseline_costs[strategy] = round(baseline_costs[strategy] + cost, 2)

    # Method 1: solver-reported optimality gap (worst across recommendations)
    optimality_gap = max(gap_samples) if gap_samples else 0.0

    # Method 4: does the recommended action survive ±20% cost-weight shifts?
    sensitivity = _sensitivity_analysis(
        main_cascade, flights_dict, airport_config, sim_engine, cost_weights
    )

    return {
        "optimality_gap_pct": round(optimality_gap, 2),
        "baseline_costs": baseline_costs,
        "sensitivity": sensitivity,
    }


def _sensitivity_analysis(cascade: dict, flights_dict: dict, airport_config: dict,
                          sim_engine, cost_weights: dict) -> dict:
    """Perturb each cost weight ±20% and check whether the rank-1 action
    type changes. stable_pct = share of perturbations with an unchanged
    recommendation; fragile_ranges lists the weights that flip it."""
    base_opt = MILPOptimizer(cost_weights).optimize(
        cascade, flights_dict, airport_config, sim_engine
    )
    base_top = base_opt["ranked_options"][0]["action_type"]

    perturb_keys = [
        "passenger_delay_per_minute", "missed_connection_per_pax",
        "gate_conflict_penalty", "aircraft_swap_cost",
    ]
    stable = 0
    total = 0
    fragile_ranges = []
    for key in perturb_keys:
        for factor in (0.8, 1.2):
            perturbed = {**cost_weights, key: cost_weights[key] * factor}
            result = MILPOptimizer(perturbed).optimize(
                cascade, flights_dict, airport_config, sim_engine
            )
            top = result["ranked_options"][0]["action_type"]
            total += 1
            if top == base_top:
                stable += 1
            else:
                fragile_ranges.append({
                    "weight": key,
                    "factor": factor,
                    "flips_to": top,
                })

    return {
        "stable_pct": round(100 * stable / total) if total else 100,
        "fragile_ranges": fragile_ranges,
        "perturbation": "±20% on 4 cost weights",
        "base_recommendation": base_top,
    }
