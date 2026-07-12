"""
Build the feature vector for one flight at inference time.

Mirrors models/training/data_pipeline.py exactly — same 26 features, same
semantics. Every value is REQUIRED, DERIVED, or ASSUMED (with a documented
default) — never invented. Missing values are passed as NaN: LightGBM
routes them natively, and "missing" is itself information the model has
seen in training (weather_data_available).

Network-state features at inference come from the scenario itself:
  - inbound_tail_delay: the delay already known/predicted for this tail's
    previous leg (scenario_runner feeds realized/predicted delays back into
    the context as it walks the schedule chronologically)
  - trailing airport state: mean of known delays among scenario flights at
    the same airport in the trailing window (a scenario-local approximation
    of the live feed a production system would have; NaN when the scenario
    carries no such information)
"""
import math
from datetime import datetime

import holidays as holidays_lib

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
    DELAY_THRESHOLD_MINUTES,
)

_US_HOLIDAYS = holidays_lib.UnitedStates(years=range(2018, 2032))
_HOLIDAY_DATES = sorted(_US_HOLIDAYS.keys())


def _parse_hhmm(time_str: str) -> datetime:
    return datetime.strptime(time_str[:5], "%H:%M")


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


def _previous_leg(flight: dict, context: dict) -> dict | None:
    """This tail's most recent leg arriving before this departure."""
    dep = _parse_hhmm(flight["scheduled_departure"])
    best = None
    for other in context.get("flights", []):
        if (
            other["tail_number"] != flight["tail_number"]
            or other["flight_id"] == flight["flight_id"]
        ):
            continue
        arr = _parse_hhmm(other["scheduled_arrival"])
        if arr < dep and (best is None or arr > _parse_hhmm(best["scheduled_arrival"])):
            best = other
    return best


def _known_delay(flight_id: str, context: dict, flights_by_id: dict) -> float | None:
    """Delay already realized/predicted for a flight in this scenario:
    scenario_runner's chronological feedback first, injected delay second."""
    realized = context.get("realized_delays", {})
    if flight_id in realized:
        return float(realized[flight_id])
    f = flights_by_id.get(flight_id, {})
    if f.get("injected_delay_minutes"):
        return float(f["injected_delay_minutes"])
    return None


def _trailing_airport_state(flight: dict, context: dict,
                            window_hours: float) -> tuple[float, float]:
    """(mean delay, delayed-share) among scenario flights departing the same
    origin within the trailing window whose delay is already known. NaN/NaN
    when the scenario provides no such observations."""
    dep = _parse_hhmm(flight["scheduled_departure"])
    flights_by_id = {f["flight_id"]: f for f in context.get("flights", [])}
    delays = []
    for other in context.get("flights", []):
        if other["flight_id"] == flight["flight_id"]:
            continue
        if other.get("origin") != flight.get("origin"):
            continue
        try:
            other_dep = _parse_hhmm(other["scheduled_departure"])
        except (KeyError, ValueError):
            continue
        gap_min = (dep - other_dep).total_seconds() / 60
        if not (0 < gap_min <= window_hours * 60):
            continue
        known = _known_delay(other["flight_id"], context, flights_by_id)
        if known is not None:
            delays.append(known)
    if not delays:
        # Explicit live-feed override wins when a caller provides one
        state = context.get("airport_state", {})
        key = f"trailing_{int(window_hours)}h_mean_delay"
        if key in state:
            return float(state[key]), float(state.get(
                f"trailing_{int(window_hours)}h_delayed_share", math.nan))
        return math.nan, math.nan
    mean = sum(delays) / len(delays)
    share = sum(1 for d in delays if d > DELAY_THRESHOLD_MINUTES) / len(delays)
    return mean, share


def _days_to_nearest_holiday(date_str: str) -> float:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return math.nan
    best = min(abs((d - h).days) for h in _HOLIDAY_DATES)
    return float(min(best, 60))


def _categorical_code(value: str, feature: str, context: dict) -> float:
    """Integer code against the train-window level list; unseen → -1
    (LightGBM treats negative categorical codes as missing)."""
    levels = context.get("categorical_levels", {}).get(feature, [])
    try:
        return float(levels.index(value))
    except ValueError:
        return -1.0


def build_feature_vector(flight: dict, context: dict, feature_names: list) -> list:
    """Return the numeric feature vector in the exact order of feature_names."""
    dep = _parse_hhmm(flight["scheduled_departure"])
    flights_by_id = {f["flight_id"]: f for f in context.get("flights", [])}

    same_tail = [
        f for f in context.get("flights", [])
        if f["tail_number"] == flight["tail_number"]
        and f["flight_id"] != flight["flight_id"]
    ]
    downstream = len([
        f for f in same_tail if _parse_hhmm(f["scheduled_departure"]) > dep
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

    origin_wx = flight.get("origin_weather_severity")
    dest_wx = flight.get("destination_weather_severity")
    origin_cg = CONGESTION_MAP[flight["origin_congestion"]]

    # Network state (scenario-local; see module docstring)
    mean2, share2 = _trailing_airport_state(flight, context, 2)
    mean4, _ = _trailing_airport_state(flight, context, 4)
    prev_leg = _previous_leg(flight, context)
    if prev_leg is None:
        inbound_delay = 0.0  # first leg of the day, per training convention
    else:
        known = _known_delay(prev_leg["flight_id"], context, flights_by_id)
        inbound_delay = float(known) if known is not None else 0.0

    feature_vector = {
        "origin_weather_severity": _nan_if_none(origin_wx),
        "dest_weather_severity": _nan_if_none(dest_wx),
        "origin_congestion_numeric": origin_cg,
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
        "weather_x_congestion": _nan_if_none(origin_wx) * origin_cg
        if origin_wx is not None else math.nan,
        "trailing_2h_airport_mean_delay": mean2,
        "trailing_4h_airport_mean_delay": mean4,
        "trailing_2h_delayed_flight_share": share2,
        "inbound_tail_delay": inbound_delay,
        # Scenario weather plays the role of a forecast: the operator supplies
        # expected conditions before departure, matching the TAF-trained rows
        "weather_is_forecast": 1.0,
        "weather_data_available": 1.0 if origin_wx is not None
        or dest_wx is not None else 0.0,
        "is_federal_holiday": 1.0 if _is_holiday(flight.get("flight_date")) else 0.0,
        "days_to_nearest_holiday": _days_to_nearest_holiday(
            flight.get("flight_date", "")
        ),
        "carrier": _categorical_code(flight["carrier_code"], "carrier", context),
        "origin_airport": _categorical_code(flight["origin"], "origin_airport", context),
        "dest_airport": _categorical_code(
            flight["destination"], "dest_airport", context
        ),
    }

    return [feature_vector[name] for name in feature_names]


def _nan_if_none(v) -> float:
    return math.nan if v is None else float(v)


def _is_holiday(date_str) -> bool:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date() in _US_HOLIDAYS
    except (TypeError, ValueError):
        return False
