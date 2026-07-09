"""
The no-hallucination enforcement layer.

Every field entering the pipeline is tagged with provenance:
  user_provided   — came from the scenario input
  derived         — computed deterministically from known fields
  assumed_default — statistical default, disclosed with its source/method

REQUIRED fields with no safe default (aircraft_type is the canonical example)
are rejected with a clear error rather than guessed.
"""
from datetime import datetime, timedelta

from config import (
    BOARDING_RATE,
    CAPACITY_MAP,
    DEFAULT_CAPACITY,
    DEFAULT_CONNECTION_BUFFER_MIN,
    DEFAULT_CONNECTION_RATE,
    DEFAULT_CREW_DUTY_HOURS_BEFORE,
    DEFAULT_LOAD_FACTOR,
    DEPLANING_RATE,
    WAKE_CATEGORY_MAP,
    WIDE_BODIES,
)

REQUIRED_FIELDS = [
    "flight_id", "carrier_code", "flight_number", "tail_number",
    "origin", "destination", "flight_date", "scheduled_departure",
    "scheduled_arrival", "aircraft_type", "assigned_gate",
    "origin_weather_severity", "destination_weather_severity",
    "origin_congestion", "destination_congestion",
]


def validate_and_complete(flight: dict, airport_config: dict) -> tuple[dict, dict]:
    """Returns (completed_flight, provenance_manifest).
    Raises ValueError for missing REQUIRED fields."""
    flight = dict(flight)  # never mutate the caller's dict
    provenance = {}

    # ─── REQUIRED fields: reject if missing ───────────────────────────────────
    for field in REQUIRED_FIELDS:
        if field not in flight or flight[field] is None:
            raise ValueError(
                f"REQUIRED field '{field}' is missing. "
                f"This field has no safe default and must be provided."
            )
        provenance[field] = "user_provided"

    # ─── DERIVED fields: computed deterministically ───────────────────────────

    # Seating capacity ← aircraft_type
    if flight.get("seating_capacity") is None:
        flight["seating_capacity"] = CAPACITY_MAP.get(
            flight["aircraft_type"], DEFAULT_CAPACITY
        )
        provenance["seating_capacity"] = "derived"
    else:
        provenance["seating_capacity"] = "user_provided"

    # Runway assignment ← weather/wind → active runway configuration
    wind_dir = flight.get("origin_wind_direction", "west")
    runway_config = airport_config.get("runway_configs", {}).get(wind_dir, {})
    flight["assigned_runway"] = runway_config.get("default_departure", "unknown")
    provenance["assigned_runway"] = "derived"

    # Wake turbulence category ← aircraft_type
    flight["wake_category"] = WAKE_CATEGORY_MAP.get(flight["aircraft_type"], "M")
    provenance["wake_category"] = "derived"

    # Body type ← aircraft_type (drives deplaning/boarding rates)
    body_type = "wide_body" if flight["aircraft_type"] in WIDE_BODIES else "narrow_body"
    flight["body_type"] = body_type
    provenance["body_type"] = "derived"

    # ─── ASSUMED-WITH-DISCLOSURE fields ───────────────────────────────────────

    # Total passengers ← seating capacity × historical load factor
    if flight.get("total_passengers") is None:
        flight["total_passengers"] = int(
            flight["seating_capacity"] * DEFAULT_LOAD_FACTOR
        )
        provenance["total_passengers"] = (
            f"assumed_default (load_factor={DEFAULT_LOAD_FACTOR})"
        )
    else:
        provenance["total_passengers"] = "user_provided"

    # Connecting passengers ← hub connection rate (DB1B aggregate)
    if flight.get("connecting_passengers") is None:
        flight["connecting_passengers"] = int(
            flight["total_passengers"] * DEFAULT_CONNECTION_RATE
        )
        provenance["connecting_passengers"] = (
            f"assumed_default (connection_rate={DEFAULT_CONNECTION_RATE})"
        )
    else:
        provenance["connecting_passengers"] = "user_provided"

    # Connection buffer ← typical MCT at a US hub
    if flight.get("avg_connection_buffer_min") is None:
        flight["avg_connection_buffer_min"] = DEFAULT_CONNECTION_BUFFER_MIN
        provenance["avg_connection_buffer_min"] = (
            f"assumed_default ({DEFAULT_CONNECTION_BUFFER_MIN:.0f} min typical MCT)"
        )
    else:
        provenance["avg_connection_buffer_min"] = "user_provided"

    # Crew duty ← assumed on duty 2h before departure
    if flight.get("crew_duty_start") is None:
        dep = datetime.strptime(flight["scheduled_departure"], "%H:%M")
        flight["crew_duty_start"] = (
            dep - timedelta(hours=DEFAULT_CREW_DUTY_HOURS_BEFORE)
        ).strftime("%H:%M")
        flight["crew_hours_on_duty"] = DEFAULT_CREW_DUTY_HOURS_BEFORE
        provenance["crew_duty_start"] = (
            f"assumed_default ({DEFAULT_CREW_DUTY_HOURS_BEFORE:.0f}hr before departure)"
        )
        provenance["crew_hours_on_duty"] = "assumed_default"
    else:
        provenance["crew_duty_start"] = "user_provided"
        if flight.get("crew_hours_on_duty") is None:
            dep = datetime.strptime(flight["scheduled_departure"], "%H:%M")
            duty_start = datetime.strptime(flight["crew_duty_start"], "%H:%M")
            hours = (dep - duty_start).total_seconds() / 3600
            flight["crew_hours_on_duty"] = round(hours if hours >= 0 else hours + 24, 1)
            provenance["crew_hours_on_duty"] = "derived"
        else:
            provenance["crew_hours_on_duty"] = "user_provided"

    if flight.get("standby_crew_available") is None:
        flight["standby_crew_available"] = True
        provenance["standby_crew_available"] = "assumed_default (True)"
    else:
        provenance["standby_crew_available"] = "user_provided"

    # ─── DERIVED from completed fields ────────────────────────────────────────

    # Deplaning/boarding time ← passengers ÷ per-minute rate for body type
    flight["estimated_deplaning_minutes"] = round(
        flight["total_passengers"] / DEPLANING_RATE[body_type], 1
    )
    flight["estimated_boarding_minutes"] = round(
        flight["total_passengers"] / BOARDING_RATE[body_type], 1
    )
    provenance["estimated_deplaning_minutes"] = "derived"
    provenance["estimated_boarding_minutes"] = "derived"

    return flight, provenance


def provenance_summary(provenance_all: dict[str, dict]) -> dict:
    """Aggregate counts across all flights: {user_provided, derived, assumed_default}."""
    counts = {"user_provided": 0, "derived": 0, "assumed_default": 0}
    for manifest in provenance_all.values():
        for tag in manifest.values():
            key = tag.split(" ")[0]
            if key in counts:
                counts[key] += 1
    return counts
