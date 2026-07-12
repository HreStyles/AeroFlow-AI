"""
Component B — discrete-event delay propagation engine.

Takes a predicted delay on one flight and propagates it through the
operational graph:
  1. Rotation cascades — the same tail's later legs inherit whatever delay
     the scheduled turnaround slack cannot absorb.
  2. Gate conflicts — a delayed departure holds its gate into the next
     occupant's window.
  3. Missed connections — connecting passengers whose buffer is smaller
     than the delay.
Returns a CascadeResult dict with all downstream impacts and the do-nothing
baseline cost priced with the scenario's configurable cost weights.
"""
from datetime import timedelta

from config import DEFAULT_COST_WEIGHTS, DOWNSTREAM_COST_DISCOUNT
from .operational_graph import OperationalGraph, parse_time, turnaround_time


class SimulationEngine:
    def __init__(self, airport_config: dict, cost_weights: dict | None = None):
        self.airport = airport_config
        self.cost_weights = {**DEFAULT_COST_WEIGHTS, **(cost_weights or {})}
        self.graph = OperationalGraph(airport_config)

    def build_operational_graph(self, flights: list[dict]) -> None:
        self.graph.build(flights)

    # Convenience accessors kept for API parity with the spec
    @property
    def rotation_graph(self):
        return self.graph.rotation_graph

    @property
    def gate_schedule(self):
        return self.graph.gate_schedule

    def propagate_delay(self, flight_id: str, delay_minutes: float,
                        flights_dict: dict,
                        skip_tails: set[str] | None = None,
                        skip_gates: set[str] | None = None) -> dict:
        """Propagate a delay through the graph.

        skip_tails / skip_gates let the optimizer re-simulate an action's
        effect (e.g. an aircraft swap decouples a tail; a gate reassignment
        removes that gate's conflict) without mutating the scenario.
        """
        skip_tails = skip_tails or set()
        skip_gates = skip_gates or set()

        results = {
            "trigger_flight": flight_id,
            "trigger_delay_minutes": round(delay_minutes, 1),
            "affected_flights": [],
            "gate_conflicts": [],
            "missed_connections": 0,
            "total_downstream_delay_minutes": 0.0,
            "baseline_cost": 0.0,
        }

        trigger = flights_dict[flight_id]
        trigger_tail = trigger["tail_number"]

        # ── 1. Rotation cascade ─────────────────────────────────────────────
        if trigger_tail not in skip_tails:
            accumulated_delay = delay_minutes
            prev_arrival = parse_time(trigger["scheduled_arrival"])
            for subsequent in self.graph.rotation_after(flight_id, trigger_tail):
                sched_dep = parse_time(subsequent["scheduled_departure"])
                min_turn = turnaround_time(subsequent["aircraft_type"], self.airport)

                scheduled_gap = (sched_dep - prev_arrival).total_seconds() / 60
                slack = scheduled_gap - min_turn

                propagated = max(0.0, accumulated_delay - max(slack, 0.0))
                if propagated <= 0:
                    break  # slack absorbed the delay; no further propagation
                results["affected_flights"].append({
                    "flight_id": subsequent["flight_id"],
                    "propagated_delay_minutes": round(propagated, 1),
                    "cause": "rotation_cascade",
                    "from_tail": trigger_tail,
                })
                results["total_downstream_delay_minutes"] += propagated
                accumulated_delay = propagated
                prev_arrival = parse_time(subsequent["scheduled_arrival"])

        # ── 2. Gate conflicts ───────────────────────────────────────────────
        trigger_gate = trigger["assigned_gate"]
        if trigger_gate in self.graph.gate_schedule and trigger_gate not in skip_gates:
            trigger_dep = parse_time(trigger["scheduled_departure"])
            delayed_dep = trigger_dep + timedelta(minutes=delay_minutes)
            for slot in self.graph.gate_schedule[trigger_gate]:
                if slot["flight_id"] == flight_id:
                    continue
                # Next occupant's window starts before we (belatedly) vacate
                if trigger_dep <= slot["start"] < delayed_dep:
                    conflict_minutes = (delayed_dep - slot["start"]).total_seconds() / 60
                    results["gate_conflicts"].append({
                        "gate": trigger_gate,
                        "conflicting_flight": slot["flight_id"],
                        "conflict_minutes": round(conflict_minutes, 1),
                    })

        # A flight explicitly declaring when its gate is next needed. The
        # delay holds the gate on both sides: a late departure vacates the
        # origin gate late, and a late arrival occupies the destination gate
        # past the next occupant's need time.
        next_needed = trigger.get("gate_next_needed_at")
        if next_needed and trigger_gate not in skip_gates:
            needed_at = parse_time(next_needed)
            trigger_dep = parse_time(trigger["scheduled_departure"])
            delayed_dep = trigger_dep + timedelta(minutes=delay_minutes)
            trigger_arr = parse_time(trigger["scheduled_arrival"])
            delayed_arr = trigger_arr + timedelta(minutes=delay_minutes)
            overrun = None
            if trigger_dep <= needed_at < delayed_dep:
                overrun = (delayed_dep - needed_at).total_seconds() / 60
            elif trigger_arr <= needed_at < delayed_arr:
                overrun = (delayed_arr - needed_at).total_seconds() / 60
            if overrun is not None:
                results["gate_conflicts"].append({
                    "gate": trigger_gate,
                    "conflicting_flight": "next_scheduled_occupant",
                    "conflict_minutes": round(overrun, 1),
                })

        # ── 3. Missed connections ───────────────────────────────────────────
        connecting = trigger.get("connecting_passengers") or 0
        buffer = trigger.get("avg_connection_buffer_min") or 60.0
        if delay_minutes > buffer and connecting > 0:
            results["missed_connections"] = connecting

        # ── 4. Do-nothing baseline cost (configurable weights) ──────────────
        results["baseline_cost"] = self._price_cascade(results, trigger)
        return results

    def _price_cascade(self, results: dict, trigger: dict) -> float:
        """Price a cascade with the v2 literature-anchored cost model:
        passenger value-of-time + aircraft direct operating cost (the delay
        costs the airline even with zero pax aboard) + itemized missed
        connections + causal gate-conflict pricing (base + per-overlap-minute)
        + crew overtime. Downstream terms carry the variance discount."""
        w = self.cost_weights
        pax = trigger.get("total_passengers") or 150
        delay = results["trigger_delay_minutes"]
        downstream = results["total_downstream_delay_minutes"]

        crew_hours = trigger.get("crew_hours_on_duty") or 0.0
        # Crew overtime accrues when the delay pushes an already-long duty day
        # past 12h (approaching the 14h FAA-style limit)
        crew_overtime_hours = max(0.0, (crew_hours + delay / 60.0) - 12.0)

        gate_conflict_cost = sum(
            w["gate_conflict_base"]
            + w["gate_conflict_per_overlap_minute"] * gc["conflict_minutes"]
            for gc in results["gate_conflicts"]
        )

        return round(
            # Trigger flight: pax time + aircraft time
            delay * (pax * w["passenger_delay_per_minute"]
                     + w["aircraft_operating_cost_per_minute"])
            + results["missed_connections"] * w["missed_connection_per_pax"]
            + gate_conflict_cost
            # Downstream flights: same two time terms, variance-discounted
            + downstream * (pax * w["passenger_delay_per_minute"]
                            + w["aircraft_operating_cost_per_minute"])
            * DOWNSTREAM_COST_DISCOUNT
            + crew_overtime_hours * w["crew_overtime_per_hour"],
            2,
        )
