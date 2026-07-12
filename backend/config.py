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
    # weather (TAF forecast when available, observed METAR otherwise, NaN when
    # neither — LightGBM routes missing values natively)
    "origin_weather_severity", "dest_weather_severity",
    "origin_congestion_numeric", "dest_congestion_numeric",
    "schedule_slack_minutes", "rotation_position",
    "downstream_legs_today", "hour_of_day", "day_of_week",
    "month", "route_avg_delay", "carrier_ontime_pct",
    "aircraft_age_years", "seating_capacity",
    "weather_x_congestion",  # interaction feature
    # network-state features (derived from already-departed flights only —
    # the system's live state, the largest signal at operational horizons)
    "trailing_2h_airport_mean_delay",
    "trailing_4h_airport_mean_delay",
    "trailing_2h_delayed_flight_share",
    "inbound_tail_delay",       # previous leg's arrival delay for this tail
    # weather metadata (missingness and forecast-vs-observed are signal)
    "weather_is_forecast",
    "weather_data_available",
    # calendar
    "is_federal_holiday",
    "days_to_nearest_holiday",
    # identity (native LightGBM categoricals, codes from saved level lists)
    "carrier",
    "origin_airport",
    "dest_airport",
]

# Passed to LightGBM's categorical_feature; encoded as integer codes against
# the level lists persisted in lookups.json (unseen level → -1 → missing)
CATEGORICAL_FEATURES = ["carrier", "origin_airport", "dest_airport"]

# TAF decision horizon: use the latest forecast issued at least this long
# before scheduled departure (an operator deciding 2h out has no later info)
TAF_HORIZON_HOURS = 2

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
# v2 — literature-anchored (engineering review §8). Every weight carries a
# derivation string surfaced in UI tooltips; these are policy inputs that a
# deployment would tune to its own economics.
DEFAULT_COST_WEIGHTS = {
    "passenger_delay_per_minute": 0.80,          # $/pax/min
    "aircraft_operating_cost_per_minute": 75.0,  # $/aircraft/min of delay
    "missed_connection_per_pax": 350.0,          # $/pax
    "crew_overtime_per_hour": 550.0,             # $/crew-hr
    "gate_conflict_base": 400.0,                 # $ per conflict (tow/re-plan)
    "gate_conflict_per_overlap_minute": 60.0,    # $ per minute of overlap
    "aircraft_swap_cost": 1500.0,                # $ per swap
    "fuel_taxi_per_minute": 18.0,                # $ per minute of excess taxi
}

COST_WEIGHT_DERIVATIONS = {
    "passenger_delay_per_minute": (
        "US DOT Revised Departmental Guidance on Valuation of Travel Time "
        "(2016): ~$48/hr for air passengers ÷ 60 min ≈ $0.80/pax-min"
    ),
    "aircraft_operating_cost_per_minute": (
        "Airlines for America (A4A) direct aircraft operating cost "
        "≈ $100/block-minute (2023, US pax carriers); EUROCONTROL/Univ. of "
        "Westminster reference values €80–110/min. Conservative $75/min for "
        "at-gate delay (no airborne fuel burn)"
    ),
    "missed_connection_per_pax": (
        "Itemized reaccommodation: rebooking ≈ $150 + hotel/meals ≈ $120 + "
        "goodwill ≈ $80 ≈ $350/pax. EU261 statutory €250–600 is the "
        "international upper bound (Bratu & Barnhart 2005 for pax-delay framing)"
    ),
    "crew_overtime_per_hour": (
        "Narrowbody crew (2 pilots + 4 FA) fully-loaded ≈ $1,300/block-hr × "
        "~40% overtime-premium exposure ≈ $550/hr"
    ),
    "gate_conflict_base": (
        "Fixed component per conflict: tow/repositioning $200–400 + ramp "
        "re-planning ≈ $400"
    ),
    "gate_conflict_per_overlap_minute": (
        "Variable component: arriving aircraft held on taxiway ≈ $60/min "
        "(taxi fuel + aircraft time + queue knock-on), scaled by simulated "
        "overlap minutes — makes the penalty causal rather than flat"
    ),
    "aircraft_swap_cost": (
        "Tow + dispatch re-release + new flight plan + crew brief + schedule "
        "perturbation risk ≈ $1,500. Thin literature — operator-tunable, "
        "low-confidence anchor (disclosed)"
    ),
    "fuel_taxi_per_minute": (
        "737-800 taxi burn ≈ 10–12 kg/min × ~$0.90/kg jet-A ≈ $10/min + "
        "engine-time maintenance reserve ≈ $8/min ≈ $18/min"
    ),
}

# ─── Pipeline thresholds ─────────────────────────────────────────────────────
DELAY_PROBABILITY_THRESHOLD = 0.3   # only log/simulate predictions above this
MIN_MEANINGFUL_DELAY_MINUTES = 5    # only propagate delays above this
CASCADE_COST_THRESHOLD = 500.0      # only run the optimizer above this cost

# Downstream cascade delay is priced at a discount vs the trigger flight's own
# delay (downstream pax counts are estimates, not observed).
DOWNSTREAM_COST_DISCOUNT = 0.5

# Distribution-aware optimization: candidate actions are costed at the P10,
# P50, and P90 predicted delays and ranked by the weighted expected cost —
# a 3-point quadrature over the predictive distribution. Weights follow the
# standard light/middle/tail split for symmetric 3-point rules.
QUANTILE_WEIGHTS = {"p10": 0.25, "p50": 0.50, "p90": 0.25}

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
