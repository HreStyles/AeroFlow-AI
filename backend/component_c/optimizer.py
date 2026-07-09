"""
Component C — MILP optimization engine (Google OR-Tools).

Evaluates candidate response actions via re-simulation + the configurable
cost function, and solves the gate-assignment sub-problem exactly as a
binary assignment MILP:
    variables    x[f,g] = 1 iff flight f is assigned to gate g
    objective    minimize reassignment cost
    constraints  one gate per flight; overlapping flights can't share a gate;
                 aircraft-gate type compatibility
Returns ranked options with expected cost, cost reduction %, delay impact,
downstream impact rating, success probability, optimality gap %, feasibility
checks, and a human-readable rationale.
"""
import time

from ortools.linear_solver import pywraplp

from config import DEFAULT_COST_WEIGHTS, MILP_SOLVERS, MILP_TIME_LIMIT_MS
from component_b.operational_graph import parse_time, turnaround_time
from .action_generator import generate_candidate_actions
from .cost_function import compute_action_cost


def create_solver():
    for name in MILP_SOLVERS:
        solver = pywraplp.Solver.CreateSolver(name)
        if solver:
            return solver, name
    return None, None


class MILPOptimizer:
    def __init__(self, cost_weights: dict | None = None):
        self.cost_weights = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}

    def optimize(self, cascade_result: dict, flights: dict,
                 airport_config: dict, simulation_engine) -> dict:
        """Rank feasible responses to a cascade, cheapest first."""
        candidates = generate_candidate_actions(cascade_result, flights, airport_config)

        milp_result = self._solve_gate_assignment_milp(
            cascade_result, flights, airport_config
        )

        evaluated = []
        for candidate in candidates:
            cost, feasibility, sim_result = compute_action_cost(
                candidate, cascade_result, flights, airport_config,
                simulation_engine, self.cost_weights,
            )
            if feasibility["all_satisfied"]:
                evaluated.append({
                    "action": candidate,
                    "expected_cost": cost,
                    "feasibility_checks": feasibility,
                    "sim_result": sim_result,
                })

        # Do-nothing competes on cost like any other option — an action that
        # costs more than absorbing the disruption must never outrank it.
        evaluated.append({
            "action": {"type": "do_nothing",
                       "description": "Hold and absorb — no action taken"},
            "expected_cost": cascade_result["baseline_cost"],
            "feasibility_checks": {
                "gate_compatible": True, "aircraft_type_match": True,
                "crew_legal": True, "all_satisfied": True,
            },
            "sim_result": dict(cascade_result),
        })
        evaluated.sort(key=lambda x: x["expected_cost"])

        ranked = []
        baseline = cascade_result["baseline_cost"]
        for i, e in enumerate(evaluated[:4]):
            reduction = ((baseline - e["expected_cost"]) / baseline * 100) if baseline > 0 else 0.0
            delay_avoided = (
                cascade_result["total_downstream_delay_minutes"]
                - e["sim_result"].get(
                    "total_downstream_delay_minutes",
                    cascade_result["total_downstream_delay_minutes"],
                )
            )
            ranked.append({
                "rank": i + 1,
                "action": e["action"].get("description", str(e["action"]["type"])),
                "action_type": e["action"]["type"],
                "action_details": e["action"],
                "expected_cost": round(e["expected_cost"], 2),
                "cost_reduction_pct": round(reduction, 1),
                "delay_impact_minutes": round(-delay_avoided, 1),
                "downstream_impact": self._classify_impact(e["sim_result"]),
                "success_probability": self._estimate_success_prob(e),
                "optimality_gap_pct": milp_result.get("gap_pct") or 0.0,
                "feasibility_checks": {
                    k: v for k, v in e["feasibility_checks"].items()
                    if k != "all_satisfied"
                },
                "rationale": self._generate_rationale(e, cascade_result),
            })

        return {
            "ranked_options": ranked,
            "optimality_gap_pct": milp_result.get("gap_pct") or 0.0,
            "solver_time_seconds": milp_result.get("solve_time", 0.0),
            "solver_status": milp_result.get("status", "unknown"),
            "milp_assignments": milp_result.get("assignments", {}),
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
    def _estimate_success_prob(evaluated: dict) -> float:
        """Success probability decreases with action complexity."""
        action_type = evaluated["action"].get("type", "")
        base = 0.92
        if "gate" in action_type:
            base -= 0.04
        if "swap" in action_type:
            base -= 0.10
        if "rebook" in action_type:
            base -= 0.05
        if action_type == "do_nothing":
            base = 0.99  # doing nothing always "succeeds" (at full cost)
        return round(base, 2)

    @staticmethod
    def _generate_rationale(evaluated: dict, cascade: dict) -> list[str]:
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
            rationale.append(
                f"Proactively rebooks {cascade.get('missed_connections', 0)} "
                f"at-risk connections"
            )
        saving = cascade["baseline_cost"] - evaluated["expected_cost"]
        if saving > 0:
            rationale.append(f"Reduces disruption cost by ${saving:,.0f}")
        return rationale
