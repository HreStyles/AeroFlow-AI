"""
Configurable weighted cost function for candidate actions.

Weights always come from the scenario config (falling back to documented
defaults) — never hardcoded here. Each action's cost is computed by
re-simulating the cascade with the action's structural effect applied
(gate freed, tail decoupled, passengers rebooked) and pricing the residual
disruption plus the action's own execution cost.
"""
from config import DEFAULT_COST_WEIGHTS, MAX_CREW_DUTY_HOURS
from component_b.airport_models import gate_compatible


def _leaf_actions(action: dict) -> list[dict]:
    """Flatten a (possibly combined) action into its component actions."""
    if "components" in action:
        return action["components"]
    return [action]


def check_feasibility(action: dict, cascade_result: dict, flights: dict,
                      airport_config: dict) -> dict:
    """Hard-constraint checks. crew_legal uses completed crew-duty fields
    against a 14h FAA-style flight duty period limit."""
    checks = {"gate_compatible": True, "aircraft_type_match": True, "crew_legal": True}

    trigger = flights.get(cascade_result["trigger_flight"], {})
    residual_delay = cascade_result.get("trigger_delay_minutes", 0.0)

    for leaf in _leaf_actions(action):
        if leaf["type"] == "gate_reassignment":
            flight = flights.get(leaf["flight_id"], {})
            checks["gate_compatible"] &= gate_compatible(
                airport_config, leaf["to_gate"], flight.get("aircraft_type", "")
            )
        elif leaf["type"] == "aircraft_swap":
            flight = flights.get(leaf["flight_id"], {})
            spare = next(
                (f for f in flights.values()
                 if f.get("tail_number") == leaf["to_tail"]), None
            )
            checks["aircraft_type_match"] &= bool(
                spare and spare.get("aircraft_type") == flight.get("aircraft_type")
            )

    # Crew legality on the trigger flight: duty hours + delay must stay under limit
    crew_hours = trigger.get("crew_hours_on_duty")
    if crew_hours is not None:
        projected = crew_hours + residual_delay / 60.0
        if projected > MAX_CREW_DUTY_HOURS:
            # Standby crew can take over — otherwise the plan is not crew-legal
            checks["crew_legal"] = bool(trigger.get("standby_crew_available", True))

    checks["all_satisfied"] = all(
        v for k, v in checks.items() if k != "all_satisfied"
    )
    return checks


def compute_action_cost(action: dict, cascade_result: dict, flights: dict,
                        airport_config: dict, simulation_engine,
                        cost_weights: dict | None = None) -> tuple[float, dict, dict]:
    """Returns (expected_cost, feasibility_checks, sim_result_under_action)."""
    w = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}
    trigger_id = cascade_result["trigger_flight"]
    delay = cascade_result.get("trigger_delay_minutes", 0.0)

    feasibility = check_feasibility(action, cascade_result, flights, airport_config)

    if action.get("type") == "do_nothing":
        return cascade_result["baseline_cost"], feasibility, dict(cascade_result)

    # Structural effects of the action on the propagation graph
    skip_tails: set[str] = set()
    skip_gates: set[str] = set()
    rebooked_pax = 0
    execution_cost = 0.0

    for leaf in _leaf_actions(action):
        if leaf["type"] == "gate_reassignment":
            # Trigger vacates its conflicted gate → that gate's conflicts vanish.
            skip_gates.add(leaf.get("from_gate", ""))
            # Towing/repositioning cost ≈ 10 min of excess taxi
            execution_cost += 10 * w["fuel_taxi_per_minute"]
        elif leaf["type"] == "aircraft_swap":
            # Downstream legs fly on the spare tail → rotation cascade is cut.
            skip_tails.add(flights[trigger_id]["tail_number"])
            execution_cost += w["aircraft_swap_cost"]
        elif leaf["type"] == "passenger_rebook":
            rebooked_pax = leaf.get("passenger_count", 0)
            # Proactive rebooking costs ~15% of a missed-connection blowup
            execution_cost += rebooked_pax * w["missed_connection_per_pax"] * 0.15

    # Re-simulate the cascade with the action's effects applied
    sim_result = simulation_engine.propagate_delay(
        trigger_id, delay, flights, skip_tails=skip_tails, skip_gates=skip_gates
    )
    if rebooked_pax:
        # Rebooked passengers no longer miss their connections
        sim_result["missed_connections"] = max(
            0, sim_result["missed_connections"] - rebooked_pax
        )
        trigger = flights[trigger_id]
        sim_result["baseline_cost"] = simulation_engine._price_cascade(
            sim_result, trigger
        )

    expected_cost = round(sim_result["baseline_cost"] + execution_cost, 2)
    return expected_cost, feasibility, sim_result
