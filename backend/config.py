"""
AeroFlow AI — central configuration.

All constants, aircraft data tables, cost weights, and feature names live here.
Paths resolve relative to this file so the app works regardless of CWD.
"""
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AIRPORTS_DIR = DATA_DIR / "airports"
PRESETS_DIR = DATA_DIR / "presets"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
VALIDATION_DIR = DATA_DIR / "validation"
DECISIONS_LOG_PATH = DATA_DIR / "decisions.jsonl"

MODELS_DIR = BASE_DIR / "models" / "saved"
CLASSIFIER_PATH = MODELS_DIR / "classifier.txt"
# LightGBM trains one booster per quantile objective; "quantile.txt" is the
# base name — actual files are quantile_p10.txt / quantile_p50.txt / quantile_p90.txt.
QUANTILE_PATH = MODELS_DIR / "quantile.txt"
LOOKUPS_PATH = MODELS_DIR / "lookups.json"
EVALUATION_REPORT_PATH = PROCESSED_DATA_DIR / "evaluation_report.json"
SHAP_GLOBAL_PATH = MODELS_DIR / "shap_global.json"

MODEL_NOT_TRAINED_MESSAGE = (
    "Model not yet trained — run the training pipeline first "
    "(scripts/download_bts.sh, scripts/download_noaa.sh, then scripts/train_all.py)."
)

# ─── Feature names (exact order used in training AND inference) ──────────────
FEATURE_NAMES = [
    "origin_weather_severity", "dest_weather_severity",
    "origin_congestion_numeric", "dest_congestion_numeric",
    "schedule_slack_minutes", "rotation_position",
    "downstream_legs_today", "hour_of_day", "day_of_week",
    "month", "route_avg_delay", "carrier_ontime_pct",
    "aircraft_age_years", "seating_capacity",
    "weather_x_congestion",  # interaction feature
]

# ─── Aircraft data tables (published figures) ────────────────────────────────
# Typical single-class-equivalent seating capacity
CAPACITY_MAP = {
    "A320": 180, "A321": 220, "B737-800": 189, "B737-900": 215,
    "B757-200": 200, "B767-300": 269, "B777-200": 314, "B777-300": 396,
    "B787-8": 248, "B787-9": 296, "A330-200": 253, "A330-300": 300,
    "A350-900": 325, "E175": 76, "CRJ-900": 76,
}
DEFAULT_CAPACITY = 180

# Minimum turnaround time in minutes by aircraft type
TURNAROUND_MAP = {
    "A320": 35, "A321": 40, "B737-800": 35, "B737-900": 38,
    "B757-200": 45, "B767-300": 55, "B777-200": 65, "B777-300": 70,
    "B787-8": 60, "B787-9": 65, "A330-200": 60, "A330-300": 65,
    "A350-900": 65, "E175": 30, "CRJ-900": 28,
}
DEFAULT_TURNAROUND = 40

# ICAO wake turbulence category
WAKE_CATEGORY_MAP = {
    "A320": "M", "A321": "M", "B737-800": "M", "B737-900": "M",
    "B757-200": "M", "B767-300": "H", "B777-200": "H", "B777-300": "H",
    "B787-8": "H", "B787-9": "H", "A330-200": "H", "A330-300": "H",
    "A350-900": "H", "E175": "M", "CRJ-900": "L",
}

WIDE_BODIES = {
    "B767-300", "B777-200", "B777-300", "B787-8", "B787-9",
    "A330-200", "A330-300", "A350-900",
}

VALID_AIRCRAFT_TYPES = sorted(CAPACITY_MAP.keys())

# Deplaning/boarding rates (passengers per minute; wide-bodies use multiple doors)
DEPLANING_RATE = {"narrow_body": 20, "wide_body": 30}
BOARDING_RATE = {"narrow_body": 12, "wide_body": 20}

# ─── Assumed-with-disclosure defaults ────────────────────────────────────────
DEFAULT_LOAD_FACTOR = 0.84            # BTS aggregate domestic load factor
ROUTE_LOAD_FACTORS = {
    "domestic_hub": 0.87,
    "domestic_regional": 0.79,
    "international": 0.82,
}
DEFAULT_CONNECTION_RATE = 0.30        # share of pax connecting at a hub (DB1B)
DEFAULT_CONNECTION_BUFFER_MIN = 55.0  # typical MCT at a US hub
DEFAULT_CREW_DUTY_HOURS_BEFORE = 2.0  # crew assumed on duty 2h before departure
MAX_CREW_DUTY_HOURS = 14.0            # FAA Part 117-style flight duty period limit

# ─── Congestion mapping ──────────────────────────────────────────────────────
CONGESTION_MAP = {"low": 0.2, "moderate": 0.5, "high": 0.75, "severe": 1.0}
CONGESTION_LEVELS = list(CONGESTION_MAP.keys())

# ─── Cost function weights (defaults; always overridable per scenario) ───────
DEFAULT_COST_WEIGHTS = {
    "passenger_delay_per_minute": 2.50,   # $/pax/min
    "missed_connection_per_pax": 300.0,   # $/pax
    "crew_overtime_per_hour": 500.0,      # $/crew-hr
    "gate_conflict_penalty": 1000.0,      # $ per conflict
    "aircraft_swap_cost": 1200.0,         # $ per swap
    "fuel_taxi_per_minute": 50.0,         # $ per minute of excess taxi
}

# ─── Pipeline thresholds ─────────────────────────────────────────────────────
DELAY_PROBABILITY_THRESHOLD = 0.3   # only log/simulate predictions above this
MIN_MEANINGFUL_DELAY_MINUTES = 5    # only propagate delays above this
CASCADE_COST_THRESHOLD = 500.0      # only run the optimizer above this cost

# Downstream cascade delay is priced at a discount vs the trigger flight's own
# delay (downstream pax counts are estimates, not observed).
DOWNSTREAM_COST_DISCOUNT = 0.5

# Confidence normalization: a P90-P10 spread of this many minutes → 0 confidence
CONFIDENCE_SPREAD_NORM_MINUTES = 180.0

# ─── Prediction / feature-lookup fallbacks (documented defaults) ─────────────
DEFAULT_ROUTE_AVG_DELAY = 15.0     # min, national average arrival delay
DEFAULT_CARRIER_ONTIME_PCT = 0.78  # national average on-time performance
DEFAULT_AIRCRAFT_AGE_YEARS = 8.0   # US fleet average
DEFAULT_SCHEDULE_SLACK = 30.0      # min, when tail has no previous leg
DEFAULT_DAY_OF_WEEK = 4            # Friday (0=Mon)
DEFAULT_MONTH = 7                  # July (peak season)

# ─── Reference codes for validation ──────────────────────────────────────────
SUPPORTED_AIRPORTS = ["ATL", "JFK"]
VALID_AIRPORT_CODES = [
    "ATL", "JFK", "LAX", "ORD", "DFW", "DEN", "SFO", "SEA", "LAS", "MCO",
    "EWR", "CLT", "PHX", "IAH", "MIA", "BOS", "MSP", "FLL", "DTW", "PHL",
    "LGA", "BWI", "SLC", "SAN", "IAD", "DCA", "MDW", "TPA", "PDX", "STL",
]
VALID_CARRIER_CODES = ["DL", "AA", "UA", "WN", "B6", "AS", "NK", "F9", "HA", "G4"]

# Weather severity → VMC/IMC boundary (severity above this ⇒ instrument conditions)
IMC_WEATHER_SEVERITY_THRESHOLD = 0.5
# Advanced weather → IMC thresholds (FAA VFR minima-ish)
IMC_VISIBILITY_MILES = 3.0
IMC_CEILING_FEET = 1000.0

# ─── MILP solver ─────────────────────────────────────────────────────────────
MILP_TIME_LIMIT_MS = 5000
MILP_SOLVERS = ["SCIP", "CBC"]  # try in order

# ─── Delay classification threshold (BTS convention) ─────────────────────────
DELAY_THRESHOLD_MINUTES = 15
