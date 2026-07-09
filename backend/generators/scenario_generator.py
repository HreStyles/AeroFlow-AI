"""
Monte Carlo scenario generator.

Samples weather severity, congestion levels, flight counts, and rotation
tightness from realistic distributions to produce randomized but plausible
scenarios. Used to stress-test the pipeline across the distribution of
realistic disruptions and to source candidate preset scenarios.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from config import CONGESTION_LEVELS  # noqa: E402
from generators.synthetic_schedules import generate_schedule  # noqa: E402

DISRUPTION_CAUSES = ["weather", "mechanical", "atc_ground_stop", "late_aircraft", "crew"]


def _severity_sample(rng: random.Random) -> float:
    """Weather severity ~ Beta(1.6, 3.2): most days are benign, storms are
    the long right tail. Occasionally force a severe event so the generated
    pool contains the disruptions we actually care about."""
    if rng.random() < 0.15:
        return round(rng.uniform(0.7, 0.95), 2)
    return round(min(0.95, rng.betavariate(1.6, 3.2)), 2)


def _congestion_for_hour(hour: int, rng: random.Random) -> str:
    """Congestion follows the diurnal bank structure of a hub."""
    if 6 <= hour < 9 or 15 <= hour < 20:
        weights = [0.05, 0.25, 0.45, 0.25]   # peak banks
    elif 9 <= hour < 15:
        weights = [0.2, 0.45, 0.3, 0.05]
    else:
        weights = [0.6, 0.3, 0.1, 0.0]
    return rng.choices(CONGESTION_LEVELS, weights=weights)[0]


def generate_scenario(airport_config: dict, seed: int | None = None,
                      scenario_index: int = 0) -> dict:
    """Produce one randomized but plausible Scenario dict."""
    rng = random.Random(seed)
    airport = airport_config["airport_code"]

    origin_wx = _severity_sample(rng)
    dest_regional_wx = _severity_sample(rng)
    n_tails = rng.randint(3, 8)
    rotation_tightness = rng.betavariate(2.5, 2.0)  # skews moderately tight

    flights = generate_schedule(
        airport_config, n_tails=n_tails,
        rotation_tightness=rotation_tightness, rng=rng,
    )

    for f in flights:
        dep_hour = int(f["scheduled_departure"][:2])
        at_hub = f["origin"] == airport
        hub_wx = origin_wx
        away_wx = round(min(0.95, max(0.0, rng.gauss(dest_regional_wx, 0.15))), 2)
        f["origin_weather_severity"] = hub_wx if at_hub else away_wx
        f["destination_weather_severity"] = away_wx if at_hub else hub_wx
        f["origin_congestion"] = _congestion_for_hour(dep_hour, rng)
        f["destination_congestion"] = _congestion_for_hour((dep_hour + 3) % 24, rng)

    # Inject a disruption into one tight-rotation flight (60% of scenarios)
    if flights and rng.random() < 0.6:
        target = rng.choice(flights)
        target["injected_delay_cause"] = rng.choice(DISRUPTION_CAUSES)
        target["injected_delay_minutes"] = int(rng.lognormvariate(3.5, 0.5))
        target["injected_delay_time"] = target["scheduled_departure"]

    # GDP event in 20% of scenarios with meaningful weather
    gdp_events = []
    if origin_wx > 0.5 and rng.random() < 0.2:
        start = rng.randint(13, 17)
        gdp_events.append({
            "airport": airport,
            "start_time": f"{start:02d}:00",
            "end_time": f"{start + rng.randint(2, 4):02d}:00",
            "reduced_acceptance_rate": rng.choice([30, 40, 50]),
        })

    return {
        "scenario_id": f"mc_{airport.lower()}_{scenario_index:05d}",
        "scenario_name": f"Monte Carlo {airport} #{scenario_index}",
        "description": (
            f"Generated scenario: hub weather severity {origin_wx}, "
            f"{n_tails} tails, rotation tightness {rotation_tightness:.2f}."
        ),
        "airport": airport,
        "flights": flights,
        "gdp_events": gdp_events,
        "cost_weights": None,
    }


def generate_pool(airport_config: dict, n: int = 100, seed: int = 42) -> list[dict]:
    """Generate a pool of n scenarios with reproducible per-scenario seeds."""
    return [
        generate_scenario(airport_config, seed=seed + i, scenario_index=i)
        for i in range(n)
    ]
