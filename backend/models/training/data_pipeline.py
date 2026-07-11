"""
Training data pipeline — five real datasets:

  1. BTS On-Time Performance  (data/raw/bts_ontime/*.zip, Jan–Jul 2024)
       → flight records + delay labels for flights touching ATL or JFK
  2. NOAA/IEM METAR           (data/raw/noaa_metar/K{ATL,JFK}_2024.csv)
       → hourly 0–1 weather severity, joined at scheduled hour
  3. FAA Aircraft Registry    (data/raw/faa_registry/ReleasableAircraft.zip)
       → tail number → aircraft model, year built (age), seat count
  4. BTS T-100 Segment        (data/raw/bts_t100/*.zip)
       → route-level average seats and load factor
  5. BTS DB1B O&D Survey      (data/raw/bts_db1b/*.zip, Q1 2024)
       → connection rate at ATL / JFK (share of passengers connecting)
       NOTE: DB1B contains no schedule-time fields, so an average
       connection *buffer* cannot be derived from it; the buffer remains a
       documented MCT default in the completeness layer.

Temporal causality is enforced: every feature is computable strictly before
the flight's scheduled departure (schedule structure, weather at the
scheduled hour, and historical aggregates from the TRAINING window only).
Actual times / delays / cancellations are used ONLY as labels.

Split is TIME-BASED, never random: train = Jan–May 2024, test = Jun–Jul 2024.

Outputs:
  data/processed/train.parquet, test.parquet
  models/saved/lookups.json   (route averages, carrier OTP, aircraft
                               registry, T-100 route stats, DB1B connection
                               rates — used at inference time)
"""
import glob
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    DEFAULT_CAPACITY,
    DEFAULT_TURNAROUND,
    DELAY_THRESHOLD_MINUTES,
    FEATURE_NAMES,
    LOOKUPS_PATH,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    TURNAROUND_MAP,
)

STUDY_AIRPORTS = ["ATL", "JFK"]
TRAIN_CUTOFF = "2024-06-01"          # train < cutoff ≤ test (time-based!)
DATA_START, DATA_END = "2024-01-01", "2024-08-01"

ONTIME_DIR = RAW_DATA_DIR / "bts_ontime"
T100_DIR = RAW_DATA_DIR / "bts_t100"
DB1B_DIR = RAW_DATA_DIR / "bts_db1b"
METAR_DIR = RAW_DATA_DIR / "noaa_metar"
FAA_DIR = RAW_DATA_DIR / "faa_registry"

ONTIME_COLUMNS = [
    "FlightDate", "Reporting_Airline", "Tail_Number",
    "Flight_Number_Reporting_Airline", "Origin", "Dest",
    "CRSDepTime", "CRSArrTime",
    "ArrDelayMinutes", "Cancelled", "Diverted",
]
# Post-hoc columns — used ONLY to build labels, never as features.
LEAKY_COLUMNS = ["DepTime", "DepDelay", "DepDelayMinutes", "ArrTime",
                 "ArrDelay", "ArrDelayMinutes", "Cancelled", "Diverted",
                 "TaxiOut", "TaxiIn", "WheelsOff", "WheelsOn", "ActualElapsedTime"]


# ─── 1. BTS On-Time Performance ──────────────────────────────────────────────

def load_ontime() -> pd.DataFrame:
    paths = sorted(glob.glob(str(ONTIME_DIR / "*.zip")))
    if not paths:
        raise FileNotFoundError(f"No BTS On-Time zips in {ONTIME_DIR}")
    frames = []
    for path in paths:
        with zipfile.ZipFile(path) as z:  # zips also contain a readme.html
            csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(
                    f, usecols=lambda c: c in ONTIME_COLUMNS, low_memory=False
                )
        df = df[df["Origin"].isin(STUDY_AIRPORTS) | df["Dest"].isin(STUDY_AIRPORTS)]
        frames.append(df)
        print(f"  {Path(path).name}: kept {len(df):,} ATL/JFK rows")
    ontime = pd.concat(frames, ignore_index=True)
    ontime["FlightDate"] = pd.to_datetime(ontime["FlightDate"])
    ontime = ontime[
        (ontime["FlightDate"] >= DATA_START) & (ontime["FlightDate"] < DATA_END)
    ]
    print(f"  total: {len(ontime):,} flights touching ATL/JFK, "
          f"{ontime['FlightDate'].min().date()} → {ontime['FlightDate'].max().date()}")
    return ontime


# ─── 2. NOAA / IEM METAR → hourly weather severity ──────────────────────────

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
    gust = row.get("gust")
    wind = max(v for v in (sknt, gust, 0.0) if pd.notna(v))
    if wind > 35:
        severity = max(severity, 0.85)
    elif wind > 25:
        severity = max(severity, 0.6)
    elif wind > 15:
        severity = max(severity, 0.3)
    skyl1 = row.get("skyl1")
    if pd.notna(skyl1) and str(row.get("skyc1", "")) in ("BKN", "OVC", "VV"):
        if skyl1 < 500:
            severity = max(severity, 0.7)
        elif skyl1 < 1000:
            severity = max(severity, 0.5)
    p01i = row.get("p01i")
    if pd.notna(p01i) and p01i > 0:
        severity = max(severity, min(0.9, 0.4 + float(p01i) * 2))
    wx = str(row.get("wxcodes", "") or "")
    if any(code in wx for code in ("TS", "GR", "FC", "+RA")):
        severity = max(severity, 0.85)
    elif any(code in wx for code in ("SN", "PL", "FZ", "IC")):
        severity = max(severity, 0.7)
    return round(severity, 2)


def load_metar() -> pd.DataFrame:
    paths = sorted(glob.glob(str(METAR_DIR / "*.csv")))
    if not paths:
        raise FileNotFoundError(f"No METAR CSVs in {METAR_DIR}")
    frames = []
    for path in paths:
        df = pd.read_csv(path, na_values=["M"], low_memory=False)
        frames.append(df)
        print(f"  {Path(path).name}: {len(df):,} observations")
    metar = pd.concat(frames, ignore_index=True)

    metar["valid"] = pd.to_datetime(metar["valid"], errors="coerce")
    metar = metar.dropna(subset=["valid"])
    metar = metar[(metar["valid"] >= DATA_START) & (metar["valid"] < DATA_END)]
    # IEM uses 'T' for trace precipitation
    metar["p01i"] = pd.to_numeric(metar["p01i"].replace("T", 0.005), errors="coerce")
    for col in ("vsby", "sknt", "gust", "skyl1"):
        metar[col] = pd.to_numeric(metar[col], errors="coerce")
    # station 'ATL'/'JFK' already IATA-like in IEM exports
    metar["airport"] = metar["station"].str.replace("^K", "", regex=True)

    # Forward-fill slowly-changing variables within station (short sensor gaps)
    metar = metar.sort_values(["airport", "valid"])
    for col in ("vsby", "sknt", "skyl1"):
        metar[col] = metar.groupby("airport")[col].ffill(limit=6)

    metar["weather_severity"] = metar.apply(_metar_severity, axis=1)
    metar["hour"] = metar["valid"].dt.floor("h")
    hourly = (
        metar.groupby(["airport", "hour"])["weather_severity"].max().reset_index()
    )
    cov = hourly.groupby("airport")["hour"].agg(["min", "max", "count"])
    print(f"  hourly severity table:\n{cov}")
    return hourly


# ─── 3. FAA Aircraft Registry ────────────────────────────────────────────────

def _normalize_model(mfr: str, model: str) -> str | None:
    """Map an FAA registry model string onto the system's aircraft-type
    vocabulary (used for turnaround-time lookups)."""
    m = model.upper().replace(" ", "")
    for pattern, target in [
        (r"737-?8", "B737-800"), (r"737-?9", "B737-900"),
        (r"757-?2", "B757-200"), (r"767-?3", "B767-300"),
        (r"777-?2", "B777-200"), (r"777-?3", "B777-300"),
        (r"787-?8", "B787-8"), (r"787-?9", "B787-9"),
        (r"A330-?2", "A330-200"), (r"A330-?3", "A330-300"),
        (r"A350", "A350-900"), (r"A321", "A321"), (r"A320", "A320"),
        (r"ERJ-?17|EMB-?170|EMB-?175|E175", "E175"),
        (r"CL-?600-?2D24|CRJ-?9", "CRJ-900"),
    ]:
        if re.search(pattern, m):
            return target
    return None


def load_faa_registry() -> dict[str, dict]:
    zpath = next(iter(glob.glob(str(FAA_DIR / "*.zip"))), None)
    if not zpath:
        raise FileNotFoundError(f"No FAA registry zip in {FAA_DIR}")
    with zipfile.ZipFile(zpath) as z:
        with z.open("MASTER.txt") as f:
            master = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8-sig"),
                usecols=lambda c: c.strip() in ("N-NUMBER", "MFR MDL CODE", "YEAR MFR"),
                dtype=str, low_memory=False,
            )
        with z.open("ACFTREF.txt") as f:
            ref = pd.read_csv(
                io.TextIOWrapper(f, encoding="utf-8-sig"),
                usecols=lambda c: c.strip() in ("CODE", "MFR", "MODEL", "NO-SEATS"),
                dtype=str, low_memory=False,
            )
    master.columns = [c.strip() for c in master.columns]
    ref.columns = [c.strip() for c in ref.columns]
    master["MFR MDL CODE"] = master["MFR MDL CODE"].str.strip()
    ref["CODE"] = ref["CODE"].str.strip()
    joined = master.merge(ref, left_on="MFR MDL CODE", right_on="CODE", how="left")

    joined["tail"] = "N" + joined["N-NUMBER"].str.strip()
    joined["year_built"] = pd.to_numeric(joined["YEAR MFR"], errors="coerce")
    joined["seats"] = pd.to_numeric(joined["NO-SEATS"], errors="coerce")

    registry: dict[str, dict] = {}
    for row in joined.itertuples(index=False):
        entry: dict = {}
        if pd.notna(row.year_built) and 1950 < row.year_built <= 2024:
            entry["age_years"] = round(2024 - float(row.year_built), 1)
        if pd.notna(row.seats) and row.seats >= 50:  # airliners only
            entry["seats"] = int(row.seats)
        model = _normalize_model(str(row.MFR or ""), str(row.MODEL or ""))
        if model:
            entry["model"] = model
        if entry:
            registry[row.tail] = entry
    print(f"  registry: {len(registry):,} tails with age/seats/model "
          f"(from {len(joined):,} records)")
    return registry


# ─── 4. BTS T-100 Segment ────────────────────────────────────────────────────

def load_t100() -> dict[str, dict]:
    zpath = next(iter(glob.glob(str(T100_DIR / "*.zip"))), None)
    if not zpath:
        raise FileNotFoundError(f"No T-100 zip in {T100_DIR}")
    usecols = ["DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "ORIGIN", "DEST",
               "YEAR", "MONTH", "CLASS"]
    t100 = pd.read_csv(zpath, usecols=usecols, low_memory=False)
    t100 = t100[
        (t100["YEAR"] == 2024)
        & (t100["CLASS"] == "F")            # scheduled passenger service
        & (t100["SEATS"] > 0)
        & (t100["DEPARTURES_PERFORMED"] > 0)
        & (t100["ORIGIN"].isin(STUDY_AIRPORTS) | t100["DEST"].isin(STUDY_AIRPORTS))
    ]
    grouped = t100.groupby(["ORIGIN", "DEST"]).agg(
        seats=("SEATS", "sum"),
        pax=("PASSENGERS", "sum"),
        deps=("DEPARTURES_PERFORMED", "sum"),
    )
    route_stats = {
        f"{o}_{d}": {
            "load_factor": round(min(1.0, r.pax / r.seats), 3),
            "avg_seats": round(r.seats / r.deps, 1),
        }
        for (o, d), r in grouped.iterrows()
    }
    print(f"  T-100: {len(route_stats):,} ATL/JFK routes "
          f"(overall load factor "
          f"{t100['PASSENGERS'].sum() / t100['SEATS'].sum():.3f})")
    return route_stats


# ─── 5. BTS DB1B O&D Survey ──────────────────────────────────────────────────

def load_db1b() -> dict[str, dict]:
    """Connection rate at each study airport from DB1B itinerary records.

    Record layout (pipe-delimited, variable length): 10 header fields
    [rec_id, carrier, yearquarter, n_coupons, passengers, origin,
     break, market_id, 0, wac] then 11 fields per coupon, whose 7th field is
    the coupon destination and 8th the trip-break indicator — a BLANK break
    means the passenger CONNECTED at that airport; 'X' means the trip ended.
    """
    zpath = next(iter(glob.glob(str(DB1B_DIR / "*.zip"))), None)
    if not zpath:
        raise FileNotFoundError(f"No DB1B zip in {DB1B_DIR}")

    stats = {ap: {"connecting": 0.0, "origin": 0.0, "terminating": 0.0}
             for ap in STUDY_AIRPORTS}
    n_rows = n_bad = 0
    with zipfile.ZipFile(zpath) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            for raw in f:
                n_rows += 1
                parts = raw.decode("ascii", "replace").rstrip("\n").split("|")
                if len(parts) < 21 or (len(parts) - 10) % 11 != 0:
                    n_bad += 1
                    continue
                try:
                    n_coupons = int(parts[3])
                    pax = float(parts[4])
                except ValueError:
                    n_bad += 1
                    continue
                origin = parts[5]
                if origin in stats:
                    stats[origin]["origin"] += pax
                for k in range(n_coupons):
                    base = 10 + 11 * k
                    if base + 7 >= len(parts):
                        break
                    dest = parts[base + 6]
                    trip_break = parts[base + 7].strip()
                    if dest in stats:
                        if trip_break == "" and k < n_coupons - 1:
                            stats[dest]["connecting"] += pax
                        else:
                            stats[dest]["terminating"] += pax

    result = {}
    for ap, s in stats.items():
        local = s["origin"] + s["terminating"]
        total = local + s["connecting"]
        result[ap] = {
            "connection_rate": round(s["connecting"] / total, 3) if total else 0.30,
            "connecting_pax_sample": int(s["connecting"]),
            "local_pax_sample": int(local),
            "source": "DB1B 2024Q1 (10% ticket sample)",
        }
        print(f"  DB1B {ap}: connection rate {result[ap]['connection_rate']:.1%} "
              f"({int(s['connecting']):,} connecting vs {int(local):,} local)")
    print(f"  DB1B parsed {n_rows:,} itinerary records ({n_bad:,} skipped)")
    return result


# ─── Feature engineering ─────────────────────────────────────────────────────

def _hhmm_to_minutes(series: pd.Series) -> pd.Series:
    v = pd.to_numeric(series, errors="coerce").fillna(0).astype(int)
    return ((v // 100) % 24) * 60 + (v % 100)


def build_features(ontime: pd.DataFrame, weather_hourly: pd.DataFrame,
                   registry: dict, route_stats: dict) -> pd.DataFrame:
    df = ontime.copy()
    df = df[(df["Cancelled"] != 1) & (df["Diverted"] != 1)]
    df = df.dropna(subset=["ArrDelayMinutes", "Tail_Number"])

    # Labels (post-hoc — never features)
    df["label_delayed"] = (df["ArrDelayMinutes"] > DELAY_THRESHOLD_MINUTES).astype(int)
    df["label_delay_minutes"] = df["ArrDelayMinutes"].clip(lower=0)

    # Schedule-time features
    dep_min = _hhmm_to_minutes(df["CRSDepTime"])
    arr_min = _hhmm_to_minutes(df["CRSArrTime"])
    df["dep_minute_of_day"] = dep_min
    df["hour_of_day"] = dep_min / 60.0
    df["day_of_week"] = df["FlightDate"].dt.weekday.astype(float)
    df["month"] = df["FlightDate"].dt.month.astype(float)

    # Aircraft rotations reconstructed from tail sequences per day
    df = df.sort_values(["Tail_Number", "FlightDate", "dep_minute_of_day"])
    grp = df.groupby(["Tail_Number", "FlightDate"], sort=False)
    df["rotation_position"] = grp.cumcount() + 1.0
    df["downstream_legs_today"] = (
        grp["Tail_Number"].transform("size") - df["rotation_position"]
    )
    # Schedule slack: gap since previous leg's scheduled arrival minus minimum
    # turnaround (per aircraft model when the registry knows it)
    prev_arr = grp["CRSArrTime"].shift(1)
    prev_arr_min = _hhmm_to_minutes(prev_arr)
    gap = df["dep_minute_of_day"] - prev_arr_min
    gap[prev_arr.isna() | (gap < 0) | (gap > 720)] = np.nan  # first leg / overnight

    tail_model = df["Tail_Number"].map(
        lambda t: registry.get(t, {}).get("model")
    )
    min_turn = tail_model.map(
        lambda m: TURNAROUND_MAP.get(m, DEFAULT_TURNAROUND)
    ).astype(float)
    df["schedule_slack_minutes"] = (gap - min_turn).fillna(30.0)

    # Registry features: aircraft age + seating capacity per tail
    df["aircraft_age_years"] = df["Tail_Number"].map(
        lambda t: registry.get(t, {}).get("age_years", np.nan)
    )
    df["aircraft_age_years"] = df["aircraft_age_years"].fillna(
        df["aircraft_age_years"].median()
    )
    tail_seats = df["Tail_Number"].map(lambda t: registry.get(t, {}).get("seats"))
    route_seats = (df["Origin"] + "_" + df["Dest"]).map(
        lambda r: route_stats.get(r, {}).get("avg_seats")
    )
    df["seating_capacity"] = (
        tail_seats.fillna(route_seats).fillna(DEFAULT_CAPACITY).astype(float)
    )

    # Weather at the scheduled local hour (both ATL and JFK are US/Eastern,
    # matching the IEM export timezone)
    df["dep_hour_ts"] = df["FlightDate"] + pd.to_timedelta(dep_min // 60, unit="h")
    df["arr_hour_ts"] = df["FlightDate"] + pd.to_timedelta(arr_min // 60, unit="h")
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
    # Weather is only observed at ATL/JFK; the other endpoint of each flight
    # gets a benign climatological default (documented assumption).
    df["origin_weather_severity"] = df["origin_weather_severity"].fillna(0.15)
    df["dest_weather_severity"] = df["dest_weather_severity"].fillna(0.15)

    # Congestion proxy inputs: scheduled ops in the same hour at the airport.
    # The raw counts are pure schedule data (known in advance → causal). The
    # p95 NORMALIZER, however, is a fitted constant and therefore must be
    # computed on the training window only — that happens in
    # split_and_aggregate, alongside route averages, to avoid split leakage.
    dep_counts = df.groupby(["Origin", "dep_hour_ts"]).size().rename("dep_count")
    df = df.merge(dep_counts, on=["Origin", "dep_hour_ts"], how="left")
    arr_counts = df.groupby(["Dest", "arr_hour_ts"]).size().rename("arr_count")
    df = df.merge(arr_counts, on=["Dest", "arr_hour_ts"], how="left")
    return df


def split_and_aggregate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Time-based split (train Jan–May, test Jun–Jul) + historical aggregates
    computed on the TRAINING window only, applied to both splits."""
    cutoff = pd.Timestamp(TRAIN_CUTOFF)
    train = df[df["FlightDate"] < cutoff].copy()
    test = df[df["FlightDate"] >= cutoff].copy()
    print(f"  time-based split at {TRAIN_CUTOFF}: "
          f"train={len(train):,} (Jan–May), test={len(test):,} (Jun–Jul)")

    route_avg = (
        train.groupby(["Origin", "Dest"])["label_delay_minutes"].mean().round(2)
    )
    carrier_otp = (
        (1 - train.groupby("Reporting_Airline")["label_delayed"].mean()).round(3)
    )
    route_map = {f"{o}_{d}": float(v) for (o, d), v in route_avg.items()}
    carrier_map = {c: {"ontime_pct": float(v)} for c, v in carrier_otp.items()}

    # Congestion p95 normalizers — TRAIN ONLY (fitted constants must never see
    # the test window; same rule as route averages). Unseen airports fall back
    # to the train-wide global p95.
    dep_p95 = train.groupby("Origin")["dep_count"].quantile(0.95).clip(lower=1)
    arr_p95 = train.groupby("Dest")["arr_count"].quantile(0.95).clip(lower=1)
    dep_global = max(float(train["dep_count"].quantile(0.95)), 1.0)
    arr_global = max(float(train["arr_count"].quantile(0.95)), 1.0)
    dep_p95_map = {k: float(v) for k, v in dep_p95.items()}
    arr_p95_map = {k: float(v) for k, v in arr_p95.items()}

    for frame in (train, test):
        frame["route_avg_delay"] = (
            (frame["Origin"] + "_" + frame["Dest"]).map(route_map).fillna(15.0)
        )
        frame["carrier_ontime_pct"] = frame["Reporting_Airline"].map(
            lambda c: carrier_map.get(c, {}).get("ontime_pct", 0.78)
        )
        frame["origin_congestion_numeric"] = (
            frame["dep_count"] / frame["Origin"].map(dep_p95_map).fillna(dep_global)
        ).clip(0, 1).round(3)
        frame["dest_congestion_numeric"] = (
            frame["arr_count"] / frame["Dest"].map(arr_p95_map).fillna(arr_global)
        ).clip(0, 1).round(3)
        frame["weather_x_congestion"] = (
            frame["origin_weather_severity"] * frame["origin_congestion_numeric"]
        )

    return train, test, {
        "route_averages": route_map,
        "carrier_stats": carrier_map,
        "congestion_p95": {
            "departures_per_hour": dep_p95_map,
            "arrivals_per_hour": arr_p95_map,
            "global_departures": dep_global,
            "global_arrivals": arr_global,
            "note": "train-window-only 95th-percentile hourly ops; divide "
                    "scheduled ops/hr by these to reproduce the congestion "
                    "features at inference time",
        },
    }


# ─── Orchestration ───────────────────────────────────────────────────────────

def run() -> dict:
    print("[1/6] BTS On-Time Performance…")
    ontime = load_ontime()
    print("[2/6] NOAA/IEM METAR…")
    weather = load_metar()
    print("[3/6] FAA aircraft registry…")
    registry = load_faa_registry()
    print("[4/6] BTS T-100 segment…")
    route_stats = load_t100()
    print("[5/6] BTS DB1B O&D survey…")
    connection_rates = load_db1b()
    print("[6/6] Feature engineering + time-based split…")
    df = build_features(ontime, weather, registry, route_stats)
    train, test, aggregates = split_and_aggregate(df)

    # Leakage audit: no post-hoc column may appear in the feature list
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

    # Inference-time lookups: only tails seen in the study data (keeps the
    # file small), plus route stats and DB1B connection rates.
    study_tails = set(df["Tail_Number"].unique())
    lookups = {
        **aggregates,
        "aircraft_registry": {
            t: registry[t] for t in study_tails if t in registry
        },
        "route_stats_t100": route_stats,
        "connection_rates_db1b": connection_rates,
    }
    LOOKUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOOKUPS_PATH, "w") as fp:
        json.dump(lookups, fp)

    print(f"  wrote {train_path} ({len(train):,}), {test_path} ({len(test):,}),")
    print(f"        {LOOKUPS_PATH} ({len(lookups['aircraft_registry']):,} tails, "
          f"{len(lookups['route_averages']):,} routes)")
    print(f"  delayed>15min base rate: train {train['label_delayed'].mean():.3f}, "
          f"test {test['label_delayed'].mean():.3f}")
    return {"train": train_path, "test": test_path, "lookups": LOOKUPS_PATH}


if __name__ == "__main__":
    run()
