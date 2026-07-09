"""
Training data pipeline: BTS On-Time Performance + NOAA/METAR weather.

Steps:
  1. Load raw BTS CSVs (data/raw/bts/*.csv or *.zip) and METAR CSVs
     (data/raw/noaa/*.csv, Iowa Environmental Mesonet format).
  2. Clean and merge on airport + hour.
  3. Feature-engineer the exact 15 features in config.FEATURE_NAMES,
     enforcing temporal causality (nothing known only after the delay
     happened may enter the feature set).
  4. Time-based train/test split (NEVER random — random splits leak future
     information into training).
  5. Persist processed matrices + historical lookup tables used at inference.

Run via scripts/train_all.py after downloading data with
scripts/download_bts.sh and scripts/download_noaa.sh.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    DELAY_THRESHOLD_MINUTES,
    FEATURE_NAMES,
    LOOKUPS_PATH,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    SUPPORTED_AIRPORTS,
    TURNAROUND_MAP,
    DEFAULT_TURNAROUND,
    CAPACITY_MAP,
    DEFAULT_CAPACITY,
)

# BTS On-Time Performance columns we need (Reporting Carrier On-Time
# Performance dataset field names).
BTS_COLUMNS = [
    "FlightDate", "Reporting_Airline", "Tail_Number", "Flight_Number_Reporting_Airline",
    "Origin", "Dest", "CRSDepTime", "DepTime", "DepDelay",
    "CRSArrTime", "ArrTime", "ArrDelay", "Cancelled", "Diverted",
]

# Columns that leak the label (known only after the fact) — these are used
# to BUILD the label and must never appear as features.
LEAKY_COLUMNS = ["DepTime", "DepDelay", "ArrTime", "ArrDelay", "Cancelled", "Diverted"]


def load_bts(raw_dir: Path | None = None) -> pd.DataFrame:
    """Load and concatenate all BTS CSVs (zipped or plain)."""
    raw_dir = Path(raw_dir or RAW_DATA_DIR / "bts")
    paths = sorted(glob.glob(str(raw_dir / "*.csv"))) + sorted(
        glob.glob(str(raw_dir / "*.zip"))
    )
    if not paths:
        raise FileNotFoundError(
            f"No BTS files in {raw_dir}. Run scripts/download_bts.sh first."
        )
    frames = []
    for path in paths:
        df = pd.read_csv(path, usecols=lambda c: c in BTS_COLUMNS, low_memory=False)
        frames.append(df)
        print(f"  loaded {path}: {len(df):,} rows")
    return pd.concat(frames, ignore_index=True)


def load_metar(raw_dir: Path | None = None) -> pd.DataFrame:
    """Load IEM ASOS/METAR CSVs → hourly weather-severity table per airport.

    IEM columns used: station, valid (timestamp), vsby (mi), sknt (wind kt),
    skyl1 (lowest ceiling ft), p01i (precip in), wxcodes.
    """
    raw_dir = Path(raw_dir or RAW_DATA_DIR / "noaa")
    paths = sorted(glob.glob(str(raw_dir / "*.csv")))
    if not paths:
        raise FileNotFoundError(
            f"No METAR files in {raw_dir}. Run scripts/download_noaa.sh first."
        )
    frames = []
    for path in paths:
        df = pd.read_csv(path, na_values=["M", "T"], low_memory=False)
        frames.append(df)
        print(f"  loaded {path}: {len(df):,} rows")
    metar = pd.concat(frames, ignore_index=True)

    metar["valid"] = pd.to_datetime(metar["valid"], errors="coerce")
    metar = metar.dropna(subset=["valid"])
    metar["hour"] = metar["valid"].dt.floor("h")
    # Missing weather handling: forward-fill within each station (weather is
    # slowly changing); missingness beyond that keeps NaN → LightGBM handles
    # missing values natively.
    metar = metar.sort_values(["station", "valid"])
    for col in ("vsby", "sknt", "skyl1", "p01i"):
        if col in metar.columns:
            metar[col] = pd.to_numeric(metar[col], errors="coerce")
            metar[col] = metar.groupby("station")[col].ffill(limit=6)

    metar["weather_severity"] = metar.apply(_metar_severity, axis=1)

    hourly = (
        metar.groupby(["station", "hour"])["weather_severity"]
        .max()
        .reset_index()
        .rename(columns={"station": "airport"})
    )
    return hourly


def _metar_severity(row) -> float:
    """Map METAR variables to the 0–1 severity index used across the system."""
    severity = 0.0
    vsby = row.get("vsby")
    if pd.notna(vsby):
        if vsby < 1:
            severity = max(severity, 0.9)
        elif vsby < 3:
            severity = max(severity, 0.6)
        elif vsby < 5:
            severity = max(severity, 0.35)
    sknt = row.get("sknt")
    if pd.notna(sknt):
        if sknt > 35:
            severity = max(severity, 0.85)
        elif sknt > 25:
            severity = max(severity, 0.6)
        elif sknt > 15:
            severity = max(severity, 0.3)
    skyl1 = row.get("skyl1")
    if pd.notna(skyl1):
        if skyl1 < 500:
            severity = max(severity, 0.7)
        elif skyl1 < 1000:
            severity = max(severity, 0.5)
    p01i = row.get("p01i")
    if pd.notna(p01i) and p01i > 0:
        severity = max(severity, min(0.9, 0.4 + float(p01i) * 2))
    wx = str(row.get("wxcodes", "") or "")
    if any(code in wx for code in ("TS", "GR", "FC")):   # thunderstorm/hail/tornado
        severity = max(severity, 0.85)
    elif any(code in wx for code in ("SN", "PL", "FZ")):  # snow/ice pellets/freezing
        severity = max(severity, 0.7)
    return round(severity, 2)


def _hhmm_to_hour(series: pd.Series) -> pd.Series:
    """BTS CRS times are integers like 1435 → 14."""
    return (pd.to_numeric(series, errors="coerce").fillna(0).astype(int) // 100) % 24


def build_features(bts: pd.DataFrame, weather_hourly: pd.DataFrame) -> pd.DataFrame:
    """Merge, clean, and engineer the 15-feature matrix + labels.

    Temporal causality: every feature is computable strictly BEFORE the
    scheduled departure — schedule structure, forecast/observed weather at
    scheduled hour, and historical aggregates computed from the TRAINING
    period only (see split_and_aggregate).
    """
    df = bts.copy()
    df = df[(df["Cancelled"] != 1) & (df["Diverted"] != 1)]
    df = df.dropna(subset=["ArrDelay", "DepDelay", "Tail_Number", "FlightDate"])
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])

    # Labels (post-hoc info — used ONLY as targets, never as features)
    df["label_delayed"] = (df["ArrDelay"] > DELAY_THRESHOLD_MINUTES).astype(int)
    df["label_delay_minutes"] = df["ArrDelay"].clip(lower=0)

    # Schedule-derived features
    df["dep_hour"] = _hhmm_to_hour(df["CRSDepTime"])
    df["hour_of_day"] = df["dep_hour"].astype(float)
    df["day_of_week"] = df["FlightDate"].dt.weekday.astype(float)
    df["month"] = df["FlightDate"].dt.month.astype(float)

    # Rotation features from tail-number sequences within each day
    df = df.sort_values(["Tail_Number", "FlightDate", "CRSDepTime"])
    grp = df.groupby(["Tail_Number", "FlightDate"])
    df["rotation_position"] = grp.cumcount() + 1.0
    df["legs_today"] = grp["Tail_Number"].transform("size").astype(float)
    df["downstream_legs_today"] = df["legs_today"] - df["rotation_position"]

    # Schedule slack: gap to previous leg's scheduled arrival minus turnaround.
    prev_arr_hour = grp["CRSArrTime"].shift(1)
    gap_minutes = (
        (pd.to_numeric(df["CRSDepTime"], errors="coerce") // 100 * 60
         + pd.to_numeric(df["CRSDepTime"], errors="coerce") % 100)
        - (pd.to_numeric(prev_arr_hour, errors="coerce") // 100 * 60
           + pd.to_numeric(prev_arr_hour, errors="coerce") % 100)
    )
    df["schedule_slack_minutes"] = (gap_minutes - DEFAULT_TURNAROUND).fillna(30.0)
    df.loc[df["schedule_slack_minutes"] < -120, "schedule_slack_minutes"] = 30.0

    # Seating capacity is unknown in BTS → national narrow-body default.
    # (Scenario inference uses the aircraft-type table instead.)
    df["seating_capacity"] = float(DEFAULT_CAPACITY)
    df["aircraft_age_years"] = 8.0

    # Weather joins (origin + destination at scheduled local hour)
    df["dep_hour_ts"] = df["FlightDate"] + pd.to_timedelta(df["dep_hour"], unit="h")
    df["arr_hour"] = _hhmm_to_hour(df["CRSArrTime"])
    df["arr_hour_ts"] = df["FlightDate"] + pd.to_timedelta(df["arr_hour"], unit="h")

    wx = weather_hourly.rename(columns={"hour": "ts"})
    df = df.merge(
        wx.rename(columns={"airport": "Origin", "ts": "dep_hour_ts",
                           "weather_severity": "origin_weather_severity"}),
        on=["Origin", "dep_hour_ts"], how="left",
    )
    df = df.merge(
        wx.rename(columns={"airport": "Dest", "ts": "arr_hour_ts",
                           "weather_severity": "dest_weather_severity"}),
        on=["Dest", "arr_hour_ts"], how="left",
    )
    # Weather stations only cover downloaded airports; elsewhere assume clear
    # but flag missingness as its own feature would in a bigger build. Here,
    # restrict training to flights touching a covered airport for label quality.
    covered = set(weather_hourly["airport"].unique())
    df = df[df["Origin"].isin(covered) | df["Dest"].isin(covered)]
    df["origin_weather_severity"] = df["origin_weather_severity"].fillna(0.1)
    df["dest_weather_severity"] = df["dest_weather_severity"].fillna(0.1)

    # Congestion proxy: scheduled departures at the airport in the same hour,
    # scaled to 0–1 within airport (pure schedule data — known in advance).
    dep_counts = df.groupby(["Origin", "dep_hour_ts"]).size().rename("dep_count")
    df = df.merge(dep_counts, on=["Origin", "dep_hour_ts"], how="left")
    origin_max = df.groupby("Origin")["dep_count"].transform("max").clip(lower=1)
    df["origin_congestion_numeric"] = (df["dep_count"] / origin_max).round(3)
    arr_counts = df.groupby(["Dest", "arr_hour_ts"]).size().rename("arr_count")
    df = df.merge(arr_counts, on=["Dest", "arr_hour_ts"], how="left")
    dest_max = df.groupby("Dest")["arr_count"].transform("max").clip(lower=1)
    df["dest_congestion_numeric"] = (df["arr_count"] / dest_max).round(3)

    df["weather_x_congestion"] = (
        df["origin_weather_severity"] * df["origin_congestion_numeric"]
    )
    return df


def split_and_aggregate(df: pd.DataFrame, test_fraction: float = 0.2
                        ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """TIME-BASED split + historical aggregates computed on TRAIN ONLY.

    Splitting by date (not randomly) prevents future flights from training a
    model evaluated on the past. Route/carrier aggregates are computed from
    the training window only, then applied to both splits — computing them on
    the full data would leak test-period outcomes into training features.
    """
    df = df.sort_values("FlightDate")
    cutoff = df["FlightDate"].quantile(1 - test_fraction)
    train = df[df["FlightDate"] <= cutoff].copy()
    test = df[df["FlightDate"] > cutoff].copy()
    print(f"  time-based split at {cutoff.date()}: "
          f"train={len(train):,}, test={len(test):,}")

    route_avg = (
        train.groupby(["Origin", "Dest"])["label_delay_minutes"].mean().round(2)
    )
    carrier_otp = (
        (1 - train.groupby("Reporting_Airline")["label_delayed"].mean()).round(3)
    )

    lookups = {
        "route_averages": {
            f"{o}_{d}": v for (o, d), v in route_avg.items()
        },
        "carrier_stats": {
            c: {"ontime_pct": v} for c, v in carrier_otp.items()
        },
        "aircraft_registry": {},
    }

    for frame in (train, test):
        frame["route_avg_delay"] = frame.apply(
            lambda r: lookups["route_averages"].get(
                f"{r['Origin']}_{r['Dest']}", 15.0
            ),
            axis=1,
        )
        frame["carrier_ontime_pct"] = frame["Reporting_Airline"].map(
            lambda c: lookups["carrier_stats"].get(c, {}).get("ontime_pct", 0.78)
        )
    return train, test, lookups


def run(raw_bts_dir: Path | None = None, raw_noaa_dir: Path | None = None) -> dict:
    """Full pipeline. Writes processed matrices + lookups; returns paths."""
    print("[1/4] Loading BTS on-time performance data…")
    bts = load_bts(raw_bts_dir)
    print("[2/4] Loading NOAA/METAR weather data…")
    weather = load_metar(raw_noaa_dir)
    print("[3/4] Merging and engineering features…")
    df = build_features(bts, weather)
    print("[4/4] Time-based split + train-only aggregates…")
    train, test, lookups = split_and_aggregate(df)

    # Audit: assert no leaky column survived into the feature list
    for col in LEAKY_COLUMNS:
        assert col not in FEATURE_NAMES, f"Label leakage: {col} in features!"
    missing = [f for f in FEATURE_NAMES if f not in train.columns]
    assert not missing, f"Missing engineered features: {missing}"

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep = FEATURE_NAMES + ["label_delayed", "label_delay_minutes", "FlightDate"]
    train_path = PROCESSED_DATA_DIR / "train.parquet"
    test_path = PROCESSED_DATA_DIR / "test.parquet"
    train[keep].to_parquet(train_path, index=False)
    test[keep].to_parquet(test_path, index=False)

    LOOKUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOOKUPS_PATH, "w") as fp:
        json.dump(lookups, fp)

    print(f"  wrote {train_path} ({len(train):,} rows), "
          f"{test_path} ({len(test):,} rows), {LOOKUPS_PATH}")
    return {"train": train_path, "test": test_path, "lookups": LOOKUPS_PATH}


if __name__ == "__main__":
    run()
