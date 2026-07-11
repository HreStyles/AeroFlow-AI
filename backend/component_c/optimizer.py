"""
Component C — MILP optimization engine (Google OR-Tools).

Distribution-aware: every candidate action is costed under the P10, P50, and
P90 predicted delays (three cascade simulations) and ranked by the weighted
expected cost E[C] = 0.25·C(P10) + 0.50·C(P50) + 0.25·C(P90) — a 3-point
quadrature over the predictive distribution. Hard-constraint feasibility
(crew legality etc.) is checked at P90, i.e. robustly against the tail.

The gate-assignment sub-problem is solved exactly as a binary MILP:
    variables    x[f,g] = 1 iff flight f is assigned to gate g
    objective    minimize reassignment cost
    constraints  one gate per flight; overlapping flights can't share a gate;
                 aircraft-gate type compatibility
Returns ranked options with expected cost (plus its per-quantile components),
cost reduction %, delay impact, downstream impact rating, optimality gap %,
feasibility checks, and a human-readable rationale.
"""
import time

from ortools.linear_solver import pywraplp

from config import (
    DEFAULT_COST_WEIGHTS,
    MILP_SOLVERS,
    MILP_TIME_LIMIT_MS,
    QUANTILE_WEIGHTS,
)
from component_b.operational_graph import parse_time, turnaround_time
from .action_generator import generate_candidate_actions
from .cost_function import compute_action_cost


def create_solver():
    for name in MILP_SOLVERS:
        solver = pywraplp.Solver.CreateSolver(name)
        if solver:
            return solver, name
    return None, None


def expected_over_quantiles(costs: dict[str, float]) -> float:
    """Weighted expected value over the 3-point delay quadrature."""
    return sum(QUANTILE_WEIGHTS[q] * costs[q] for q in QUANTILE_WEIGHTS)


class MILPOptimizer:
    def __init__(self, cost_weights: dict | None = None):
        self.cost_weights = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}

    def optimize(self, cascades: dict, flights: dict,
                 airport_config: dict, simulation_engine) -> dict:
        """Rank feasible responses, cheapest expected cost first.

        `cascades` is either {"p10": CascadeResult, "p50": …, "p90": …} —
        the same trigger delay propagated at each predicted quantile — or a
        single CascadeResult, which is treated as a degenerate (point-mass)
        distribution for backward compatibility.
        """
        if "trigger_flight" in cascades:  # single cascade → point mass
            cascades = {q: cascades for q in QUANTILE_WEIGHTS}
        c50 = cascades["p50"]
        c90 = cascades["p90"]

        # Candidates are generated from the P90 view: the tail scenario has
        # the superset of impacts (extra affected rotations, missed
        # connections), so no action relevant at any quantile is missed.
        candidates = generate_candidate_actions(c90, flights, airport_config)

        milp_result = self._solve_gate_assignment_milp(c90, flights, airport_config)

        evaluated = []
        for candidate in candidates:
            costs, sims = {}, {}
            feasibility = None
            for q, cascade_q in cascades.items():
                cost_q, feas_q, sim_q = compute_action_cost(
                    candidate, cascade_q, flights, airport_config,
                    simulation_engine, self.cost_weights,
                )
                costs[q] = cost_q
                sims[q] = sim_q
                if q == "p90":
                    feasibility = feas_q  # robust: constraints hold at the tail
            if feasibility["all_satisfied"]:
                evaluated.append({
                    "action": candidate,
                    "costs": costs,
                    "expected_cost": expected_over_quantiles(costs),
                    "feasibility_checks": feasibility,
                    "sim_result": sims["p50"],
                })

        # Do-nothing competes on expected cost like any other option — an
        # action that costs more than absorbing the disruption must never
        # outrank it.
        baseline_costs = {q: cascades[q]["baseline_cost"] for q in QUANTILE_WEIGHTS}
        expected_baseline = expected_over_quantiles(baseline_costs)
        evaluated.append({
            "action": {"type": "do_nothing",
                       "description": "Hold and absorb — no action taken"},
            "costs": baseline_costs,
            "expected_cost": expected_baseline,
            "feasibility_checks": {
                "gate_compatible": True, "aircraft_type_match": True,
                "crew_legal": True, "all_satisfied": True,
            },
            "sim_result": dict(c50),
        })
        evaluated.sort(key=lambda x: x["expected_cost"])

        ranked = []
        for i, e in enumerate(evaluated[:4]):
            reduction = (
                (expected_baseline - e["expected_cost"]) / expected_baseline * 100
                if expected_baseline > 0 else 0.0
            )
            delay_avoided = (
                c50["total_downstream_delay_minutes"]
                - e["sim_result"].get(
                    "total_downstream_delay_minutes",
                    c50["total_downstream_delay_minutes"],
                )
            )
            ranked.append({
                "rank": i + 1,
                "action": e["action"].get("description", str(e["action"]["type"])),
                "action_type": e["action"]["type"],
                "action_details": e["action"],
                "expected_cost": round(e["expected_cost"], 2),
                "expected_cost_p10": round(e["costs"]["p10"], 2),
                "expected_cost_p50": round(e["costs"]["p50"], 2),
                "expected_cost_p90": round(e["costs"]["p90"], 2),
                "cost_reduction_pct": round(reduction, 1),
                "delay_impact_minutes": round(-delay_avoided, 1),
                "downstream_impact": self._classify_impact(e["sim_result"]),
                "optimality_gap_pct": milp_result.get("gap_pct") or 0.0,
                "feasibility_checks": {
                    k: v for k, v in e["feasibility_checks"].items()
                    if k != "all_satisfied"
                },
                "rationale": self._generate_rationale(e, c50, expected_baseline),
            })

        return {
            "ranked_options": ranked,
            "optimality_gap_pct": milp_result.get("gap_pct") or 0.0,
            "solver_time_seconds": milp_result.get("solve_time", 0.0),
            "solver_status": milp_result.get("status", "unknown"),
            "milp_assignments": milp_result.get("assignments", {}),
            "evaluation": {
                "method": "expected_cost_3point_quadrature",
                "quantile_weights": dict(QUANTILE_WEIGHTS),
                "quantile_delays_minutes": {
                    q: cascades[q].get("trigger_delay_minutes")
                    for q in QUANTILE_WEIGHTS
                },
                "expected_baseline_cost": round(expected_baseline, 2),
                "feasibility_checked_at": "p90 (robust)",
            },
        }

    def _solve_gate_assignment_milp(self, cascade_result: dict, flights: dict,
                                    airport_config: dict) -> dict:
        solver, solver_name = create_solver()
        if not solver:
            return {"gap_pct": None, "solve_time": 0.0, "status": "solver_unavailable"}

        affected_ids = [cascade_result["trigger_flight"]] + [
            af["flight_id"] for af in cascade_result.get("affected_flights", [])
        ]
        affected_ids = [fid for fid in dict.fromkeys(affected_ids) if fid in flights]
        gates = airport_config.get("gates", [])
        compatibility = airport_config.get("gate_aircraft_compatibility", {})
        if not affected_ids or not gates:
            return {"gap_pct": None, "solve_time": 0.0, "status": "nothing_to_solve"}

        # Decision variables: x[f,g] ∈ {0,1}
        x = {}
        for f_id in affected_ids:
            for g in gates:
                x[f_id, g] = solver.BoolVar(f"x_{f_id}_{g}")

        # C1: each flight gets exactly one gate
        for f_id in affected_ids:
            solver.Add(sum(x[f_id, g] for g in gates) == 1)

        # C2: overlapping flights can't share a gate.  Other (non-affected)
        # flights keep their gates, so affected flights that would overlap
        # them are barred from those gates.
        for i, f1 in enumerate(affected_ids):
            for f2 in affected_ids[i + 1:]:
                if self._times_overlap(flights[f1], flights[f2], airport_config):
                    for g in gates:
                        solver.Add(x[f1, g] + x[f2, g] <= 1)
        for f_id in affected_ids:
            for other in flights.values():
                oid = other.get("flight_id")
                if oid in affected_ids or other.get("status") == "idle":
                    continue
                if self._times_overlap(flights[f_id], other, airport_config):
                    g = other.get("assigned_gate")
                    if g in gates:
                        solver.Add(x[f_id, g] == 0)

        # C3: aircraft-gate type compatibility
        for f_id in affected_ids:
            ac_type = flights[f_id].get("aircraft_type", "")
            for g in gates:
                compatible_types = compatibility.get(g, [])
                if compatible_types and ac_type not in compatible_types:
                    solver.Add(x[f_id, g] == 0)

        # Objective: prefer keeping current gates; a move costs towing/repositioning
        move_cost = 10 * self.cost_weights["fuel_taxi_per_minute"]
        objective = solver.Objective()
        for f_id in affected_ids:
            current_gate = flights[f_id].get("assigned_gate", "")
            for g in gates:
                objective.SetCoefficient(x[f_id, g], 0.0 if g == current_gate else move_cost)
        objective.SetMinimization()

        solver.SetTimeLimit(MILP_TIME_LIMIT_MS)
        t0 = time.time()
        status = solver.Solve()
        solve_time = time.time() - t0

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            best = solver.Objective().Value()
            try:
                bound = solver.Objective().BestBound()
            except Exception:
                bound = best
            gap = abs(best - bound) / max(abs(best), 1e-9) * 100 if best else 0.0
            return {
                "status": "optimal" if status == pywraplp.Solver.OPTIMAL else "feasible",
                "solver": solver_name,
                "gap_pct": round(gap, 2),
                "solve_time": round(solve_time, 3),
                "objective_value": best,
                "assignments": {
                    f_id: g
                    for f_id in affected_ids
                    for g in gates
                    if x[f_id, g].solution_value() > 0.5
                },
            }
        return {"status": "infeasible", "solver": solver_name, "gap_pct": None,
                "solve_time": round(solve_time, 3), "assignments": {}}

    @staticmethod
    def _times_overlap(f1: dict, f2: dict, airport_config: dict) -> bool:
        """Do the two flights' gate occupancy windows overlap?"""
        try:
            d1 = parse_time(f1["scheduled_departure"])
            d2 = parse_time(f2["scheduled_departure"])
        except (KeyError, ValueError):
            return False
        t1 = turnaround_time(f1.get("aircraft_type", ""), airport_config)
        t2 = turnaround_time(f2.get("aircraft_type", ""), airport_config)
        s1, e1 = d1.timestamp() - t1 * 60, d1.timestamp()
        s2, e2 = d2.timestamp() - t2 * 60, d2.timestamp()
        return s1 < e2 and s2 < e1

    @staticmethod
    def _classify_impact(sim_result: dict) -> str:
        total = sim_result.get("total_downstream_delay_minutes", 0)
        if total < 15:
            return "low"
        if total < 60:
            return "medium"
        return "high"

    @staticmethod
    def _generate_rationale(evaluated: dict, cascade: dict,
                            expected_baseline: float) -> list[str]:
        rationale = []
        action = evaluated["action"]
        action_type = str(action.get("type", ""))
        sim = evaluated["sim_result"]

        if action_type == "do_nothing":
            rationale.append("No intervention — accepts the full disruption cost")
            if cascade.get("missed_connections"):
                rationale.append(
                    f"{cascade['missed_connections']} passengers miss connections"
                )
            return rationale

        if "gate" in action_type:
            n_resolved = len(cascade.get("gate_conflicts", [])) - len(
                sim.get("gate_conflicts", [])
            )
            if n_resolved > 0:
                rationale.append(
                    f"Eliminates {n_resolved} gate conflict(s) at "
                    f"{cascade['gate_conflicts'][0]['gate']}"
                )
            else:
                rationale.append("Frees the contested gate for the next arrival")
        if "swap" in action_type:
            rationale.append("Decouples downstream flights from the delayed aircraft")
            avoided = cascade.get("total_downstream_delay_minutes", 0) - sim.get(
                "total_downstream_delay_minutes", 0
            )
            if avoided > 0:
                rationale.append(
                    f"Avoids {avoided:.0f} min of downstream rotation delay"
                )
        if "rebook" in action_type:
            leaves = action.get("components", [action])
            rebook = next((a for a in leaves if a.get("type") == "passenger_rebook"), {})
            n_pax = rebook.get("passenger_count", cascade.get("missed_connections", 0))
            rationale.append(
                f"Proactively rebooks {n_pax} connections at risk in the "
                f"P90 tail scenario"
            )
        saving = expected_baseline - evaluated["expected_cost"]
        if saving > 0:
            rationale.append(
                f"Reduces expected disruption cost by ${saving:,.0f} "
                f"(averaged over the P10/P50/P90 delay outcomes)"
            )
        costs = evaluated.get("costs", {})
        if costs and costs.get("p90", 0) > costs.get("p10", 0):
            rationale.append(
                f"Holds up across the distribution: ${costs['p10']:,.0f} if the "
                f"delay is mild (P10) to ${costs['p90']:,.0f} in the tail (P90)"
            )
        return rationale
