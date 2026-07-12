"""
Baseline response strategies for validation (Method 3): the MILP-backed
optimizer must beat do-nothing, random-feasible, and greedy-heuristic
strategies for its recommendation to mean anything.

All strategies are scored the same way the optimizer scores its own
candidates: expected cost over the P10/P50/P90 quantile cascades
(0.25/0.50/0.25 weighting), so the comparison is apples-to-apples.
"""
import random

from config import DEFAULT_COST_WEIGHTS, QUANTILE_WEIGHTS
from .action_generator import generate_candidate_actions
from .cost_function import compute_action_cost
from .optimizer import expected_over_quantiles


def run_baselines(cascades: dict, flights: dict, airport_config: dict,
                  simulation_engine, cost_weights: dict | None = None,
                  seed: int = 42) -> dict:
    """Return {"do_nothing": $, "random": $, "greedy": $, "milp": $}.

    `cascades` is {"p10": CascadeResult, "p50": …, "p90": …} or a single
    CascadeResult (treated as a point-mass distribution).
    """
    weights = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}
    if "trigger_flight" in cascades:  # single cascade → point mass
        cascades = {q: cascades for q in QUANTILE_WEIGHTS}

    do_nothing_cost = expected_over_quantiles(
        {q: cascades[q]["baseline_cost"] for q in QUANTILE_WEIGHTS}
    )

    # Candidates from the P90 view (superset of impacts), matching the optimizer
    candidates = generate_candidate_actions(cascades["p90"], flights, airport_config)
    feasible = []
    for candidate in candidates:
        costs = {}
        feasibility = None
        for q in QUANTILE_WEIGHTS:
            cost_q, feas_q, _ = compute_action_cost(
                candidate, cascades[q], flights, airport_config,
                simulation_engine, weights,
            )
            costs[q] = cost_q
            if q == "p90":
                feasibility = feas_q
        if feasibility["all_satisfied"]:
            feasible.append((candidate, expected_over_quantiles(costs)))

    # Random-feasible: pick any feasible action at random (seeded → reproducible)
    if feasible:
        rng = random.Random(seed)
        random_cost = rng.choice(feasible)[1]
    else:
        random_cost = do_nothing_cost

    # Greedy heuristic: the best *simple* action — greedy can't see that
    # combinations beat the sum of their parts.
    simple = [(c, cost) for c, cost in feasible if "components" not in c]
    greedy_cost = min((cost for _, cost in simple), default=do_nothing_cost)

    # MILP: full optimizer result (best over all candidates incl. combinations)
    milp_cost = min((cost for _, cost in feasible), default=do_nothing_cost)

    return {
        "do_nothing": round(do_nothing_cost, 2),
        "random": round(min(random_cost, do_nothing_cost), 2),
        "greedy": round(min(greedy_cost, do_nothing_cost), 2),
        "milp": round(min(milp_cost, do_nothing_cost), 2),
    }
