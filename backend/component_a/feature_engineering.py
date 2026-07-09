"""
Build the 15-feature numeric vector for one flight.

Every value is REQUIRED, DERIVED, or ASSUMED (with a documented default) —
never invented. The same function is used at inference time and mirrors the
semantics of the training feature matrix in models/training/data_pipeline.py.
"""
from datetime import datetime

from config import (
    CONGESTION_MAP,
    DEFAULT_AIRCRAFT_AGE_YEARS,
    DEFAULT_CAPACITY,
    DEFAULT_CARRIER_ONTIME_PCT,
    DEFAULT_DAY_OF_WEEK,
    DEFAULT_MONTH,
    DEFAULT_ROUTE_AVG_DELAY,
    DEFAULT_SCHEDULE_SLACK,
    DEFAULT_TURNAROUND,
)


def _parse_hhmm(time_str: str) -> datetime:
    return datetime.strptime(time_str, "%H:%M")


def compute_schedule_slack(flight: dict, context: dict) -> float:
    """Gap between this tail's previous arrival and this departure, minus the
    minimum turnaround. Positive slack absorbs upstream delay."""
    dep = _parse_hhmm(flight["scheduled_departure"])
    airport_config = context.get("airport_config", {})
    min_turnaround = airport_config.get("min_turnaround_minutes", {}).get(
        flight["aircraft_type"], DEFAULT_TURNAROUND
    )

    slack = DEFAULT_SCHEDULE_SLACK  # documented default when no previous leg
    best_prev_arr = None
    for other in context.get("flights", []):
        if (
            other["tail_number"] != flight["tail_number"]
            or other["flight_id"] == flight["flight_id"]
        ):
            continue
        prev_arr = _parse_hhmm(other["scheduled_arrival"])
        if prev_arr < dep and (best_prev_arr is None or prev_arr > best_prev_arr):
            best_prev_arr = prev_arr

    if best_prev_arr is not None:
        gap = (dep - best_prev_arr).total_seconds() / 60
        slack = gap - min_turnaround
    return slack


def build_feature_vector(flight: dict, context: dict, feature_names: list) -> list:
    """Return the numeric feature vector in the exact order of feature_names."""
    dep = _parse_hhmm(flight["scheduled_departure"])

    same_tail = [
        f for f in context.get("flights", [])
        if f["tail_number"] == flight["tail_number"]
        and f["flight_id"] != flight["flight_id"]
    ]

    downstream = len([
        f for f in same_tail
        if _parse_hhmm(f["scheduled_departure"]) > dep
    ])

    rotation_position = flight.get("rotation_position") or (
        1 + len([f for f in same_tail if _parse_hhmm(f["scheduled_departure"]) < dep])
    )

    route_key = f"{flight['origin']}_{flight['destination']}"
    route_avg = context.get("route_averages", {}).get(route_key, DEFAULT_ROUTE_AVG_DELAY)
    carrier_otp = (
        context.get("carrier_stats", {})
        .get(flight["carrier_code"], {})
        .get("ontime_pct", DEFAULT_CARRIER_ONTIME_PCT)
    )
    aircraft_age = (
        context.get("aircraft_registry", {})
        .get(flight["tail_number"], {})
        .get("age_years", DEFAULT_AIRCRAFT_AGE_YEARS)
    )

    weather_x_congestion = (
        flight["origin_weather_severity"] * CONGESTION_MAP[flight["origin_congestion"]]
    )

    feature_vector = {
        "origin_weather_severity": flight["origin_weather_severity"],
        "dest_weather_severity": flight["destination_weather_severity"],
        "origin_congestion_numeric": CONGESTION_MAP[flight["origin_congestion"]],
        "dest_congestion_numeric": CONGESTION_MAP[flight["destination_congestion"]],
        "schedule_slack_minutes": compute_schedule_slack(flight, context),
        "rotation_position": rotation_position,
        "downstream_legs_today": downstream,
        "hour_of_day": dep.hour + dep.minute / 60.0,
        "day_of_week": context.get("day_of_week", DEFAULT_DAY_OF_WEEK),
        "month": context.get("month", DEFAULT_MONTH),
        "route_avg_delay": route_avg,
        "carrier_ontime_pct": carrier_otp,
        "aircraft_age_years": aircraft_age,
        "seating_capacity": flight.get("seating_capacity") or DEFAULT_CAPACITY,
        "weather_x_congestion": weather_x_congestion,
    }

    return [feature_vector[name] for name in feature_names]
