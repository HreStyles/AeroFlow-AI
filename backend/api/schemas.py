"""
Pydantic request/response models for the AeroFlow AI API.

These are the canonical data shapes for the whole system; the frontend
TypeScript types in frontend/src/types/ mirror them 1:1.
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

from config import CONGESTION_LEVELS, VALID_AIRCRAFT_TYPES


class Flight(BaseModel):
    """A single flight in a scenario. Every field is tagged with provenance
    by the completeness layer (user_provided | derived | assumed_default)."""

    # Category 1 — Flight Identification (ALL REQUIRED)
    flight_id: str                                    # e.g., "DL2107"
    carrier_code: str                                 # IATA 2-letter, e.g., "DL"
    flight_number: int                                # e.g., 2107
    tail_number: str                                  # e.g., "N674DL"
    origin: str                                       # IATA airport code, e.g., "JFK"
    destination: str                                  # IATA airport code, e.g., "ATL"
    flight_date: str                                  # "YYYY-MM-DD"

    # Category 2 — Schedule (REQUIRED)
    scheduled_departure: str                          # "HH:MM" local time
    scheduled_arrival: str                            # "HH:MM" local time

    # Category 3 — Aircraft Information (REQUIRED: aircraft_type; rest derived)
    aircraft_type: str                                # e.g., "A321", "B737-800"
    seating_capacity: Optional[int] = None            # Derived from aircraft_type
    rotation_position: Optional[int] = None           # Derived from tail sequence

    # Category 4 — Weather (REQUIRED in at least simple mode)
    origin_weather_severity: float = Field(ge=0.0, le=1.0)
    destination_weather_severity: float = Field(ge=0.0, le=1.0)
    # Advanced weather fields (optional; override severity if provided)
    origin_visibility_miles: Optional[float] = None
    origin_wind_knots: Optional[float] = None
    origin_ceiling_feet: Optional[float] = None
    origin_precipitation: Optional[Literal["none", "rain", "snow", "ice"]] = None
    destination_visibility_miles: Optional[float] = None
    destination_wind_knots: Optional[float] = None
    destination_ceiling_feet: Optional[float] = None
    destination_precipitation: Optional[Literal["none", "rain", "snow", "ice"]] = None

    # Category 5 — Congestion (REQUIRED in simple mode)
    origin_congestion: Literal["low", "moderate", "high", "severe"]
    destination_congestion: Literal["low", "moderate", "high", "severe"]

    # Category 6 — Passengers (ASSUMED-WITH-DISCLOSURE if not provided)
    total_passengers: Optional[int] = None
    connecting_passengers: Optional[int] = None
    avg_connection_buffer_min: Optional[float] = None

    # Category 7 — Crew (ASSUMED-WITH-DISCLOSURE if not provided)
    crew_duty_start: Optional[str] = None             # "HH:MM"
    crew_hours_on_duty: Optional[float] = None
    standby_crew_available: Optional[bool] = None     # Defaults to True

    # Category 8 — Gate Assignment (REQUIRED)
    assigned_gate: str                                # e.g., "A15"
    gate_next_needed_at: Optional[str] = None         # "HH:MM"

    # Category 9 — Disruption Injection (testing only, optional)
    injected_delay_cause: Optional[Literal[
        "weather", "mechanical", "atc_ground_stop", "late_aircraft", "crew"
    ]] = None
    injected_delay_minutes: Optional[int] = None
    injected_delay_time: Optional[str] = None         # "HH:MM"

    # Fleet status marker used by the action generator ("idle" = spare aircraft)
    status: Optional[str] = None

    @field_validator("aircraft_type")
    @classmethod
    def _valid_aircraft(cls, v: str) -> str:
        if v not in VALID_AIRCRAFT_TYPES:
            raise ValueError(
                f"Unknown aircraft_type '{v}'. Valid types: {', '.join(VALID_AIRCRAFT_TYPES)}"
            )
        return v


class CostWeights(BaseModel):
    """Configurable cost function weights — exposed as sliders in the UI."""
    passenger_delay_per_minute: float = 2.50          # $/pax/min
    missed_connection_per_pax: float = 300.0          # $/pax
    crew_overtime_per_hour: float = 500.0             # $/crew-hr
    gate_conflict_penalty: float = 1000.0             # $ per conflict
    aircraft_swap_cost: float = 1200.0                # $ per swap
    fuel_taxi_per_minute: float = 50.0                # $ per minute of excess taxi


class RunwayLayout(BaseModel):
    id: str
    x1: float
    y1: float
    x2: float
    y2: float


class ConcourseLayout(BaseModel):
    id: str
    x: float
    y: float
    gates: list[str]


class MapLayout(BaseModel):
    width: float
    height: float
    runways: list[RunwayLayout]
    concourses: list[ConcourseLayout]
    taxiways: list[dict] = []


class AirportConfig(BaseModel):
    airport_code: str                                 # "ATL" or "JFK"
    airport_name: str = ""
    gates: list[str]
    gate_aircraft_compatibility: dict[str, list[str]]
    runways: list[str]
    runway_configs: dict[str, dict]                   # wind direction → active set
    vmc_capacity_per_hour: int                        # arrivals/hr, visual conditions
    imc_capacity_per_hour: int                        # arrivals/hr, instrument conditions
    min_turnaround_minutes: dict[str, int] = {}
    map_layout: Optional[MapLayout] = None


class GDPEvent(BaseModel):
    airport: str
    start_time: str                                   # "HH:MM"
    end_time: str
    reduced_acceptance_rate: int                      # arrivals/hr during GDP


class Scenario(BaseModel):
    scenario_id: str
    scenario_name: str
    # Presets store the airport as a code string ("ATL"); the API resolves it
    # to a full AirportConfig via data/airports/{code}.json before running.
    airport: Union[str, AirportConfig]
    flights: list[Flight]
    gdp_events: list[GDPEvent] = []
    cost_weights: Optional[CostWeights] = None        # defaults if not provided
    description: Optional[str] = None


EventType = Literal[
    "flight_departure",
    "flight_arrival",
    "gate_assignment",
    "delay_predicted",
    "cascade_detected",
    "recommendation_generated",
    "operator_decision",
    "disruption_injected",
    "gdp_started",
    "gdp_ended",
]


class SimEvent(BaseModel):
    """A single timestamped event in the simulation playback."""
    sim_time: str                                     # "HH:MM:SS" simulated time
    event_type: EventType
    flight_id: Optional[str] = None
    details: dict                                     # event-type-specific payload


class ValidationResults(BaseModel):
    """Validation data bundled with every scenario result."""
    optimality_gap_pct: float                         # Method 1
    baseline_costs: dict[str, float]                  # Method 3
    sensitivity: dict                                 # Method 4


class EventLog(BaseModel):
    scenario_id: str
    scenario_name: str = ""
    airport_code: str = ""
    prediction_source: str = ""
    events: list[SimEvent]
    validation: ValidationResults
    flights: list[dict] = []                          # completed flights (for map/UI)
    provenance: dict[str, dict] = {}                  # flight_id → field → provenance


class DecisionRequest(BaseModel):
    recommendation_id: str
    selected_rank: int
    decision: Literal["accepted", "overridden"]
    override_reason: Optional[str] = None
