"""
Generate realistic flight schedules for an airport-day.

Real airline rotation/crew data is proprietary; per standard practice for
airline-recovery research prototypes, we construct synthetic schedules
calibrated to realistic parameters: tail-number rotations with plausible
turnaround gaps, gate assignments respecting aircraft-gate compatibility,
and hub-appropriate carrier/route mixes.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from config import TURNAROUND_MAP, VALID_AIRPORT_CODES  # noqa: E402

HUB_CARRIERS = {"ATL": ["DL", "WN", "AA"], "JFK": ["B6", "DL", "AA"]}
COMMON_TYPES = ["A320", "A321", "B737-800", "B737-900", "E175", "CRJ-900"]
# Typical block times in minutes for short/medium domestic legs
BLOCK_TIME_RANGE = (75, 210)


def _fmt(minutes: int) -> str:
    minutes = max(0, min(23 * 60 + 59, minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _compatible_gates(airport_config: dict, aircraft_type: str) -> list[str]:
    compat = airport_config.get("gate_aircraft_compatibility", {})
    return [
        g for g in airport_config.get("gates", [])
        if not compat.get(g) or aircraft_type in compat[g]
    ]


def generate_schedule(airport_config: dict, n_tails: int = 6,
                      rotation_tightness: float = 0.5,
                      rng: random.Random | None = None) -> list[dict]:
    """Generate an airport-day of flights as scenario-ready dicts.

    rotation_tightness ∈ [0,1]: 0 → generous turnaround slack (60–90 min
    above minimum), 1 → razor-thin (0–10 min above minimum).
    """
    rng = rng or random.Random()
    airport = airport_config["airport_code"]
    carriers = HUB_CARRIERS.get(airport, ["DL", "AA", "UA"])
    other_airports = [a for a in VALID_AIRPORT_CODES if a != airport]

    flights: list[dict] = []
    used_flight_numbers: set[int] = set()

    for t in range(n_tails):
        carrier = rng.choice(carriers)
        aircraft_type = rng.choice(COMMON_TYPES)
        tail = f"N{rng.randint(100, 999)}{carrier[0]}{chr(rng.randint(65, 90))}"
        min_turn = TURNAROUND_MAP.get(aircraft_type, 40)
        gates = _compatible_gates(airport_config, aircraft_type)
        gate = rng.choice(gates) if gates else "A1"

        n_legs = rng.randint(2, 5)
        # First departure between 06:00 and 10:00
        clock = rng.randint(6 * 60, 10 * 60)
        at_hub = rng.random() < 0.5  # alternate hub-out / in-hub legs
        remote = rng.choice(other_airports)

        for leg in range(n_legs):
            block = rng.randint(*BLOCK_TIME_RANGE)
            dep, arr = clock, clock + block
            if arr >= 23 * 60:
                break
            origin, dest = (airport, remote) if at_hub else (remote, airport)
            number = rng.randint(100, 4999)
            while number in used_flight_numbers:
                number = rng.randint(100, 4999)
            used_flight_numbers.add(number)

            flights.append({
                "flight_id": f"{carrier}{number}",
                "carrier_code": carrier,
                "flight_number": number,
                "tail_number": tail,
                "origin": origin,
                "destination": dest,
                "flight_date": "2024-07-15",
                "scheduled_departure": _fmt(dep),
                "scheduled_arrival": _fmt(arr),
                "aircraft_type": aircraft_type,
                "assigned_gate": gate,
                "rotation_position": leg + 1,
            })

            # Next leg: turnaround = minimum + slack drawn from tightness
            max_extra = int(90 * (1 - rotation_tightness)) + 10
            turnaround = min_turn + rng.randint(0, max_extra)
            clock = arr + turnaround
            at_hub = not at_hub
            if at_hub:
                remote = rng.choice(other_airports)

    return flights
