"""
Airport-specific models: layout configs, runway configuration derivation from
wind/weather, and throughput capacity (VMC vs IMC rates from FAA published
airport capacity profiles).
"""
import json
from functools import lru_cache

from config import (
    AIRPORTS_DIR,
    IMC_CEILING_FEET,
    IMC_VISIBILITY_MILES,
    IMC_WEATHER_SEVERITY_THRESHOLD,
    SUPPORTED_AIRPORTS,
)


class AirportNotFoundError(KeyError):
    pass


@lru_cache(maxsize=None)
def load_airport_config(code: str) -> dict:
    """Load data/airports/{code}.json. Cached — configs are static files."""
    code = code.upper()
    path = AIRPORTS_DIR / f"{code}.json"
    if not path.exists():
        raise AirportNotFoundError(
            f"Airport '{code}' not found. Supported: {', '.join(SUPPORTED_AIRPORTS)}"
        )
    with open(path) as fp:
        return json.load(fp)


def derive_runway_config(airport_config: dict, wind_direction_degrees: float | None = None,
                         wind_label: str | None = None) -> dict:
    """Pick the active runway configuration from wind.

    Aircraft take off and land into the wind, so the flow direction follows
    the wind's compass origin: wind from 180–359° ⇒ west flow at an
    east-west runway airport; 0–179° ⇒ east flow. A textual label
    ("west"/"east") wins when provided.
    """
    configs = airport_config.get("runway_configs", {})
    if not configs:
        return {}
    if wind_label and wind_label in configs:
        return {"name": wind_label, **configs[wind_label]}

    default_name = next(iter(configs))
    if wind_direction_degrees is None:
        return {"name": default_name, **configs[default_name]}

    wind_direction_degrees %= 360
    name = "west" if 180 <= wind_direction_degrees < 360 else "east"
    if name not in configs:
        name = default_name
    return {"name": name, **configs[name]}


def is_imc(weather_severity: float | None = None, visibility_miles: float | None = None,
           ceiling_feet: float | None = None) -> bool:
    """Instrument meteorological conditions: advanced METAR fields take
    precedence over the simple severity index when provided."""
    if visibility_miles is not None and visibility_miles < IMC_VISIBILITY_MILES:
        return True
    if ceiling_feet is not None and ceiling_feet < IMC_CEILING_FEET:
        return True
    if visibility_miles is None and ceiling_feet is None and weather_severity is not None:
        return weather_severity >= IMC_WEATHER_SEVERITY_THRESHOLD
    return False


def throughput_capacity(airport_config: dict, weather_severity: float | None = None,
                        visibility_miles: float | None = None,
                        ceiling_feet: float | None = None,
                        gdp_events: list[dict] | None = None,
                        at_time: str | None = None) -> dict:
    """Arrivals/hour capacity given weather conditions and any active GDP.

    VMC and IMC rates come from FAA published airport capacity profiles
    (stored per airport in the config JSON). An active Ground Delay Program
    caps the acceptance rate below the weather-derived capacity.
    """
    imc = is_imc(weather_severity, visibility_miles, ceiling_feet)
    capacity = (
        airport_config["imc_capacity_per_hour"] if imc
        else airport_config["vmc_capacity_per_hour"]
    )
    condition = "IMC" if imc else "VMC"

    gdp_active = None
    if gdp_events and at_time:
        for gdp in gdp_events:
            if gdp["start_time"] <= at_time[:5] <= gdp["end_time"]:
                gdp_active = gdp
                capacity = min(capacity, gdp["reduced_acceptance_rate"])
                break

    return {
        "capacity_per_hour": capacity,
        "condition": condition,
        "gdp_active": gdp_active is not None,
        "gdp_rate": gdp_active["reduced_acceptance_rate"] if gdp_active else None,
    }


def gate_compatible(airport_config: dict, gate: str, aircraft_type: str) -> bool:
    """A gate with no compatibility entry accepts any type (open stand)."""
    compatible = airport_config.get("gate_aircraft_compatibility", {}).get(gate, [])
    return not compatible or aircraft_type in compatible
