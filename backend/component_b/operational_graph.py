"""
Operational dependency graph: aircraft rotations (tail numbers), gate
occupancy schedule, and passenger connection map. Component B propagates
delays along these edges.
"""
from collections import defaultdict
from datetime import datetime, timedelta

from config import DEFAULT_TURNAROUND, TURNAROUND_MAP


def parse_time(time_str: str) -> datetime:
    """Parse HH:MM (or HH:MM:SS) to a datetime on a fixed reference date."""
    time_str = time_str[:5]
    return datetime.strptime(f"2024-01-01 {time_str}", "%Y-%m-%d %H:%M")


def turnaround_time(aircraft_type: str, airport_config: dict | None = None) -> float:
    """Minimum turnaround in minutes; airport config overrides the global table."""
    if airport_config:
        override = airport_config.get("min_turnaround_minutes", {}).get(aircraft_type)
        if override is not None:
            return float(override)
    return float(TURNAROUND_MAP.get(aircraft_type, DEFAULT_TURNAROUND))


class OperationalGraph:
    """Builds and holds the dependency structures for a scenario's flights."""

    def __init__(self, airport_config: dict | None = None):
        self.airport_config = airport_config or {}
        self.rotation_graph: dict[str, list[dict]] = {}   # tail → time-ordered flights
        self.gate_schedule: dict[str, list[dict]] = {}    # gate → occupancy slots
        self.connection_map: dict[str, list[dict]] = {}   # flight_id → connecting groups

    def build(self, flights: list[dict]) -> "OperationalGraph":
        # Rotation graph: group by tail number, sort by scheduled departure
        tails = defaultdict(list)
        for f in flights:
            tails[f["tail_number"]].append(f)
        for tail in tails:
            tails[tail].sort(key=lambda x: parse_time(x["scheduled_departure"]))
        self.rotation_graph = dict(tails)

        # Gate schedule: each flight occupies its gate from (departure − turnaround)
        # to departure at the origin airport
        self.gate_schedule = {}
        for f in flights:
            gate = f["assigned_gate"]
            dep_time = parse_time(f["scheduled_departure"])
            turn = turnaround_time(f["aircraft_type"], self.airport_config)
            self.gate_schedule.setdefault(gate, []).append({
                "flight_id": f["flight_id"],
                "start": dep_time - timedelta(minutes=turn),
                "end": dep_time,
                "flight": f,
            })
        for gate in self.gate_schedule:
            self.gate_schedule[gate].sort(key=lambda s: s["start"])

        # Connection map: connecting-passenger groups on each inbound flight
        self.connection_map = {}
        for f in flights:
            connecting = f.get("connecting_passengers") or 0
            if connecting > 0:
                self.connection_map[f["flight_id"]] = [{
                    "passenger_count": connecting,
                    "buffer_minutes": f.get("avg_connection_buffer_min") or 60.0,
                }]
        return self

    def rotation_after(self, flight_id: str, tail_number: str) -> list[dict]:
        """Flights this tail flies after the given flight, in order."""
        rotation = self.rotation_graph.get(tail_number, [])
        idx = next(
            (i for i, f in enumerate(rotation) if f["flight_id"] == flight_id), -1
        )
        if idx < 0:
            return []
        return rotation[idx + 1:]
