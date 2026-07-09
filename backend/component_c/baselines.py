"""
Baseline response strategies for validation (Method 3): the MILP-backed
optimizer must beat do-nothing, random-feasible, and greedy-heuristic
strategies for its recommendation to mean anything.
"""
import random

from config import DEFAULT_COST_WEIGHTS
from .action_generator import generate_candidate_actions
from .cost_function import compute_action_cost


def run_baselines(cascade_result: dict, flights: dict, airport_config: dict,
                  simulation_engine, cost_weights: dict | None = None,
                  milp_cost: float | None = None, seed: int = 42) -> dict:
    """Return {"do_nothing": $, "random": $, "greedy": $, "milp": $}."""
    weights = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}
    do_nothing_cost = cascade_result["baseline_cost"]

    candidates = generate_candidate_actions(cascade_result, flights, airport_config)
    feasible = []
    for candidate in candidates:
        cost, feasibility, _ = compute_action_cost(
            candidate, cascade_result, flights, airport_config,
            simulation_engine, weights,
        )
        if feasibility["all_satisfied"]:
            feasible.append((candidate, cost))

    # Random-feasible: pick any feasible action at random (seeded → reproducible)
    if feasible:
        rng = random.Random(seed)
        random_cost = rng.choice(feasible)[1]
    else:
        random_cost = do_nothing_cost

    # Greedy heuristic: repeatedly take the single cheapest *simple* action.
    # (Approximated here as the best non-combined action — greedy can't see
    # that combinations beat the sum of their parts.)
    simple = [(c, cost) for c, cost in feasible if "components" not in c]
    greedy_cost = min((cost for _, cost in simple), default=do_nothing_cost)

    # MILP: full optimizer result (best over all candidates incl. combinations)
    if milp_cost is None:
        milp_cost = min((cost for _, cost in feasible), default=do_nothing_cost)

    return {
        "do_nothing": round(do_nothing_cost, 2),
        "random": round(min(random_cost, do_nothing_cost), 2),
        "greedy": round(min(greedy_cost, do_nothing_cost), 2),
        "milp": round(min(milp_cost, do_nothing_cost), 2),
    }
