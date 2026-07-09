"""
Enumerate feasible candidate actions in response to a cascade:
  1. Gate reassignment  — aircraft-gate type compatibility + availability
  2. Aircraft swap      — idle aircraft of matching type
  3. Passenger rebook   — later alternative connections
  4. Combined actions   — gate+swap, gate+swap+rebook
"""
from datetime import datetime

from component_b.airport_models import gate_compatible
from component_b.operational_graph import parse_time, turnaround_time


def generate_candidate_actions(cascade_result: dict, flights: dict,
                               airport_config: dict) -> list[dict]:
    candidates = []
    trigger_id = cascade_result["trigger_flight"]
    trigger = flights.get(trigger_id, {})

    # ── Action type 1: Gate reassignment ─────────────────────────────────────
    current_gate = trigger.get("assigned_gate", "")
    available_gates = _find_available_gates(
        trigger, flights, airport_config, exclude=[current_gate]
    )
    for gate in available_gates:
        candidates.append({
            "type": "gate_reassignment",
            "description": f"Reassign {trigger_id} to Gate {gate}",
            "flight_id": trigger_id,
            "from_gate": current_gate,
            "to_gate": gate,
        })

    # ── Action type 2: Aircraft swap for downstream flights ──────────────────
    seen_swap_flights = set()
    for affected in cascade_result.get("affected_flights", []):
        if affected["cause"] != "rotation_cascade":
            continue
        if affected["flight_id"] in seen_swap_flights:
            continue
        seen_swap_flights.add(affected["flight_id"])
        for spare in _find_spare_aircraft(affected["flight_id"], flights):
            candidates.append({
                "type": "aircraft_swap",
                "description": (
                    f"Swap aircraft for {affected['flight_id']} to {spare['tail']}"
                ),
                "flight_id": affected["flight_id"],
                "from_tail": affected.get("from_tail", ""),
                "to_tail": spare["tail"],
            })

    # ── Action type 3: Passenger rebooking ───────────────────────────────────
    if cascade_result.get("missed_connections", 0) > 0:
        alt_flights = _find_alternative_connections(trigger, flights)
        if alt_flights:
            candidates.append({
                "type": "passenger_rebook",
                "description": (
                    f"Rebook {cascade_result['missed_connections']} connecting "
                    f"passengers onto {alt_flights[0]}"
                ),
                "flight_id": trigger_id,
                "passenger_count": cascade_result["missed_connections"],
                "alternative_flights": alt_flights,
            })

    # ── Action type 4: Combined actions ──────────────────────────────────────
    gate_actions = [c for c in candidates if c["type"] == "gate_reassignment"]
    swap_actions = [c for c in candidates if c["type"] == "aircraft_swap"]
    rebook_actions = [c for c in candidates if c["type"] == "passenger_rebook"]

    if gate_actions and swap_actions:
        candidates.append({
            "type": "gate_reassignment + aircraft_swap",
            "description": (
                f"{gate_actions[0]['description']} + {swap_actions[0]['description']}"
            ),
            "components": [gate_actions[0], swap_actions[0]],
        })
    if gate_actions and swap_actions and rebook_actions:
        candidates.append({
            "type": "gate_reassignment + aircraft_swap + passenger_rebook",
            "description": (
                f"{gate_actions[0]['description']} + "
                f"{swap_actions[0]['description']} + "
                f"{rebook_actions[0]['description']}"
            ),
            "components": [gate_actions[0], swap_actions[0], rebook_actions[0]],
        })
    elif swap_actions and rebook_actions and not gate_actions:
        candidates.append({
            "type": "aircraft_swap + passenger_rebook",
            "description": (
                f"{swap_actions[0]['description']} + {rebook_actions[0]['description']}"
            ),
            "components": [swap_actions[0], rebook_actions[0]],
        })

    return candidates


def _occupancy_overlaps(f: dict, gate: str, trigger: dict,
                        airport_config: dict) -> bool:
    """Would flight f's occupancy of `gate` overlap the trigger's needed window?"""
    if f.get("assigned_gate") != gate:
        return False
    trig_dep = parse_time(trigger["scheduled_departure"])
    trig_turn = turnaround_time(trigger["aircraft_type"], airport_config)
    f_dep = parse_time(f["scheduled_departure"])
    f_turn = turnaround_time(f["aircraft_type"], airport_config)
    # Occupancy windows: [dep - turnaround, dep]; pad the trigger's window by
    # its predicted delay-ish buffer of 60 min on the vacate side.
    trig_start = trig_dep.timestamp() - trig_turn * 60
    trig_end = trig_dep.timestamp() + 60 * 60
    f_start = f_dep.timestamp() - f_turn * 60
    f_end = f_dep.timestamp()
    return f_start < trig_end and trig_start < f_end


def _find_available_gates(trigger: dict, flights: dict, airport_config: dict,
                          exclude: list, limit: int = 3) -> list[str]:
    """Gates that are (a) type-compatible and (b) unoccupied around the
    trigger's occupancy window."""
    ac_type = trigger.get("aircraft_type", "")
    available = []
    for gate in airport_config.get("gates", []):
        if gate in exclude:
            continue
        if not gate_compatible(airport_config, gate, ac_type):
            continue
        occupied = any(
            _occupancy_overlaps(f, gate, trigger, airport_config)
            for f in flights.values()
            if f.get("flight_id") != trigger.get("flight_id")
        )
        if not occupied:
            available.append(gate)
        if len(available) >= limit:
            break
    return available


def _find_spare_aircraft(flight_id: str, flights: dict, limit: int = 2) -> list[dict]:
    """Idle aircraft of the same type available for a swap."""
    flight = flights.get(flight_id, {})
    needed_type = flight.get("aircraft_type", "")
    spares = []
    for f in flights.values():
        if (
            f.get("aircraft_type") == needed_type
            and f.get("tail_number") != flight.get("tail_number")
            and f.get("status") == "idle"
        ):
            spares.append({"tail": f["tail_number"], "flight_id": f["flight_id"]})
        if len(spares) >= limit:
            break
    return spares


def _find_alternative_connections(trigger: dict, flights: dict,
                                  limit: int = 3) -> list[str]:
    """Later flights departing the trigger's destination, usable for rebooking."""
    dest = trigger.get("destination", "")
    arr = trigger.get("scheduled_arrival", "00:00")
    alternatives = []
    for f in flights.values():
        if f.get("flight_id") == trigger.get("flight_id"):
            continue
        if f.get("origin") != dest or f.get("status") == "idle":
            continue
        # Never rebook onto the disrupted aircraft's own later legs
        if f.get("tail_number") == trigger.get("tail_number"):
            continue
        try:
            if datetime.strptime(f["scheduled_departure"], "%H:%M") <= \
               datetime.strptime(arr, "%H:%M"):
                continue
        except ValueError:
            continue
        alternatives.append(f["flight_id"])
    alternatives.sort(key=lambda fid: flights[fid]["scheduled_departure"])
    return alternatives[:limit]
