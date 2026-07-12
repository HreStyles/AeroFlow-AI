"""
Training data pipeline — six real data sources:

  1. BTS On-Time Performance  (data/raw/bts_ontime/*.zip)
       years used: 2019, 2023, 2024, 2025.
       2020–2022 are EXCLUDED even if present: COVID-era operations are a
       different regime (load factors, schedule banks, and delay dynamics
       collapsed), and training on them would teach the model a world that
       no longer exists. Documented regime-break decision.
  2. NOAA/IEM METAR           (data/raw/noaa_metar/K{ATL,JFK}_{year}.csv)
       → hourly OBSERVED 0–1 weather severity
  3. NOAA/IEM TAF             (data/raw/noaa_taf/K{ATL,JFK}_taf_2024.csv)
       → FORECAST severity from the latest TAF issued ≥2h before departure.
       Fixes the observed-weather leakage: at a 2-hour decision horizon the
       system can only know a forecast, not the observation. Where no TAF
       exists (2019/2023/2025 files not downloaded, or issuance gaps) we
       fall back to observed METAR with weather_is_forecast=0 — the model
       learns that forecast-based rows are noisier.
  4. FAA Aircraft Registry    → tail → model / age / seats
  5. BTS T-100 Segment        → route-level seats + load factor
  6. BTS DB1B O&D Survey      → hub connection rates (simulation side)

Network-state features (no download — derived from BTS itself) capture the
system's live state, the dominant signal at operational horizons (Rebollo &
Balakrishnan 2014; BTS delay-cause data puts late-arriving aircraft #1):
  trailing_2h/4h_airport_mean_delay, trailing_2h_delayed_flight_share
  (rolling, computed ONLY from flights already departed at prediction time;
  BTS DepDelayMinutes is floored at 0, so with a strict "actual departure
  time < scheduled departure" window no flight can see its own outcome),
  and inbound_tail_delay (previous leg's arrival delay for the same tail).

Splits are TIME-BASED, never random:
  train      = 2019 + 2023 + 2024-01..05
  test       = 2024-06..07  (the walk-forward frontier)
  oot_2025   = 2025         (untouched out-of-time year for the
                             "tested on a different year entirely" claim)
All fitted constants (route averages, carrier OTP, congestion p95,
categorical level lists) come from the TRAIN window only.
"""
import ast
import glob
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import holidays as holidays_lib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from config import (  # noqa: E402
    CATEGORICAL_FEATURES,
    DEFAULT_CAPACITY,
    DEFAULT_TURNAROUND,
    DELAY_THRESHOLD_MINUTES,
    FEATURE_NAMES,
    LOOKUPS_PATH,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
    TAF_HORIZON_HOURS,
    TURNAROUND_MAP,
)

STUDY_AIRPORTS = ["ATL", "JFK"]
STUDY_YEARS = {2019, 2023, 2024, 2025}
COVID_YEARS = {2020, 2021, 2022}      # excluded — regime break (see docstring)
TEST_YEAR, TEST_MONTHS = 2024, {6, 7}
OOT_YEAR = 2025

ONTIME_DIR = RAW_DATA_DIR / "bts_ontime"
T100_DIR = RAW_DATA_DIR / "bts_t100"
DB1B_DIR = RAW_DATA_DIR / "bts_db1b"
METAR_DIR = RAW_DATA_DIR / "noaa_metar"
TAF_DIR = RAW_DATA_DIR / "noaa_taf"
FAA_DIR = RAW_DATA_DIR / "faa_registry"

ONTIME_COLUMNS = [
    "FlightDate", "Reporting_Airline", "Tail_Number",
    "Flight_Number_Reporting_Airline", "Origin", "Dest",
    "CRSDepTime", "CRSArrTime",
    "DepDelayMinutes",  # used ONLY (a) as trailing-window state of flights
                        # that already departed, (b) never for the same row
    "ArrDelayMinutes", "Cancelled", "Diverted",
]
# Post-hoc columns of the SAME flight — labels only, never same-row features.
LEAKY_COLUMNS = ["DepTime", "DepDelay", "ArrTime",
                 "ArrDelay", "ArrDelayMinutes", "Cancelled", "Diverted",
                 "TaxiOut", "TaxiIn", "WheelsOff", "WheelsOn",
                 "ActualElapsedTime"]

US_HOLIDAYS = holidays_lib.UnitedStates(years=range(2018, 2027))
HOLIDAY_DATES = pd.DatetimeIndex(sorted(US_HOLIDAYS.keys()))


# ─── 1. BTS On-Time Performance (multi-year, chunked per zip) ────────────────

def load_ontime() -> pd.DataFrame:
    paths = sorted(glob.glob(str(ONTIME_DIR / "*.zip")))
    if not paths:
        raise FileNotFoundError(f"No BTS On-Time zips in {ONTIME_DIR}")
    frames = []
    skipped_covid = 0
    for path in paths:
        m = re.search(r"_(\d{4})_(\d{1,2})\.zip$", Path(path).name)
        year = int(m.group(1)) if m else 0
        if year in COVID_YEARS:
            skipped_covid += 1
            continue
        if year not in STUDY_YEARS:
            continue
        with zipfile.ZipFile(path) as z:  # zips also contain a readme.html
            csv_name = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(csv_name) as f:
                df = pd.read_csv(
                    f, usecols=lambda c: c in ONTIME_COLUMNS, low_memory=False
                )
        df = df[df["Origin"].isin(STUDY_AIRPORTS) | df["Dest"].isin(STUDY_AIRPORTS)]
        frames.append(df)
    if skipped_covid:
        print(f"  skipped {skipped_covid} COVID-era (2020–22) files by design")
    ontime = pd.concat(frames, ignore_index=True)
    ontime["FlightDate"] = pd.to_datetime(ontime["FlightDate"])
    ontime = ontime[ontime["FlightDate"].dt.year.isin(STUDY_YEARS)]
    by_year = ontime["FlightDate"].dt.year.value_counts().sort_index()
    print(f"  {len(ontime):,} ATL/JFK flights: "
          + ", ".join(f"{y}={n:,}" for y, n in by_year.items()))
    return ontime


# ─── 2. METAR (observed) ─────────────────────────────────────────────────────

def _metar_severity(row) -> float:
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
        frames.append(pd.read_csv(path, na_values=["M"], low_memory=False))
    metar = pd.concat(frames, ignore_index=True)

    metar["valid"] = pd.to_datetime(metar["valid"], errors="coerce")
    metar = metar.dropna(subset=["valid"])
    metar = metar[metar["valid"].dt.year.isin(STUDY_YEARS)]
    metar["p01i"] = pd.to_numeric(metar["p01i"].replace("T", 0.005), errors="coerce")
    for col in ("vsby", "sknt", "gust", "skyl1"):
        metar[col] = pd.to_numeric(metar[col], errors="coerce")
    metar["airport"] = metar["station"].str.replace("^K", "", regex=True)
    metar = metar.sort_values(["airport", "valid"])
    for col in ("vsby", "sknt", "skyl1"):
        metar[col] = metar.groupby("airport")[col].ffill(limit=6)

    metar["weather_severity"] = metar.apply(_metar_severity, axis=1)
    metar["hour"] = metar["valid"].dt.floor("h")
    hourly = (
        metar.groupby(["airport", "hour"])["weather_severity"].max().reset_index()
    )
    cov = hourly.groupby("airport")["hour"].agg(
        lambda s: f"{s.min():%Y-%m} → {s.max():%Y-%m} ({len(s):,}h)"
    )
    for ap, desc in cov.items():
        print(f"  METAR {ap}: {desc}")
    return hourly


# ─── 3. TAF (forecast) ───────────────────────────────────────────────────────

def _parse_list(s) -> list:
    try:
        v = ast.literal_eval(s) if isinstance(s, str) else []
        return v if isinstance(v, list) else []
    except (ValueError, SyntaxError):
        return []


def _taf_severity(row) -> float:
    """Same 0–1 severity formula as METAR, on TAF forecast fields."""
    severity = 0.0
    vsby = row.get("visibility")
    if pd.notna(vsby):
        if vsby < 1:
            severity = max(severity, 0.9)
        elif vsby < 3:
            severity = max(severity, 0.6)
        elif vsby < 5:
            severity = max(severity, 0.35)
    wind = max(v for v in (row.get("sknt"), row.get("gust"), 0.0) if pd.notna(v))
    if wind > 35:
        severity = max(severity, 0.85)
    elif wind > 25:
        severity = max(severity, 0.6)
    elif wind > 15:
        severity = max(severity, 0.3)
    # Lowest broken/overcast layer = forecast ceiling
    ceiling = None
    for cover, level in zip(row["skyc_list"], row["skyl_list"]):
        if cover in ("BKN", "OVC", "VV") and level is not None:
            ceiling = level if ceiling is None else min(ceiling, level)
    if ceiling is not None:
        if ceiling < 500:
            severity = max(severity, 0.7)
        elif ceiling < 1000:
            severity = max(severity, 0.5)
    wx = " ".join(str(w) for w in row["wx_list"])
    if any(code in wx for code in ("TS", "GR", "FC", "+RA")):
        severity = max(severity, 0.85)
    elif any(code in wx for code in ("SN", "PL", "FZ", "IC")):
        severity = max(severity, 0.7)
    return round(severity, 2)


def load_taf() -> pd.DataFrame:
    """Return TAF forecast periods: airport, issue_ts, fx_start, fx_end,
    is_tempo, severity. fx_end for FM/base groups = next group's start
    within the same issuance (TAF semantics)."""
    paths = sorted(glob.glob(str(TAF_DIR / "*.csv")))
    if not paths:
        print("  no TAF files — all rows will use observed METAR fallback")
        return pd.DataFrame(
            columns=["airport", "issue_ts", "fx_start", "fx_end",
                     "is_tempo", "severity"]
        )
    frames = []
    for path in paths:
        frames.append(pd.read_csv(path, low_memory=False))
    taf = pd.concat(frames, ignore_index=True)

    taf["issue_ts"] = pd.to_datetime(taf["valid"], errors="coerce")
    taf["fx_start"] = pd.to_datetime(taf["fx_valid"], errors="coerce")
    taf["fx_end_raw"] = pd.to_datetime(taf["fx_valid_end"], errors="coerce")
    taf = taf.dropna(subset=["issue_ts", "fx_start"])
    taf["airport"] = taf["station"].str.replace("^K", "", regex=True)
    taf["is_tempo"] = taf["is_tempo"].astype(str).str.lower() == "true"
    for col in ("sknt", "gust", "visibility"):
        taf[col] = pd.to_numeric(taf[col], errors="coerce")
    taf["skyc_list"] = taf["skyc"].map(_parse_list)
    taf["skyl_list"] = taf["skyl"].map(_parse_list)
    taf["wx_list"] = taf["presentwx"].map(_parse_list)
    taf["severity"] = taf.apply(_taf_severity, axis=1)

    # FM/base groups run until the next base group of the same issuance;
    # the last group runs to issuance + 30h (max TAF validity)
    taf = taf.sort_values(["airport", "issue_ts", "fx_start"])
    base = taf[~taf["is_tempo"]].copy()
    base["fx_end"] = (
        base.groupby(["airport", "issue_ts"])["fx_start"].shift(-1)
    )
    base["fx_end"] = base["fx_end"].fillna(base["issue_ts"] + pd.Timedelta(hours=30))
    tempo = taf[taf["is_tempo"]].copy()
    tempo["fx_end"] = tempo["fx_end_raw"].fillna(
        tempo["fx_start"] + pd.Timedelta(hours=1)
    )
    periods = pd.concat([base, tempo], ignore_index=True)[
        ["airport", "issue_ts", "fx_start", "fx_end", "is_tempo", "severity"]
    ]
    n_issuances = periods.groupby("airport")["issue_ts"].nunique()
    print("  TAF issuances: "
          + ", ".join(f"{a}={n:,}" for a, n in n_issuances.items()))
    return periods


def join_taf_severity(flights: pd.DataFrame, taf_periods: pd.DataFrame,
                      airport_col: str, ts_col: str) -> pd.Series:
    """Forecast severity for each flight from the latest TAF issued
    ≥ TAF_HORIZON_HOURS before the flight's timestamp; NaN when no such
    TAF covers the timestamp. TEMPO groups raise severity to their max
    (a forecast of possible worse conditions is planning-relevant)."""
    result = pd.Series(np.nan, index=flights.index)
    if taf_periods.empty:
        return result
    horizon = pd.Timedelta(hours=TAF_HORIZON_HOURS)
    for airport, fl in flights.groupby(airport_col):
        periods = taf_periods[taf_periods["airport"] == airport]
        if periods.empty:
            continue
        issuances = np.sort(periods["issue_ts"].unique())
        t = fl[ts_col]
        # latest issuance at or before (t − horizon)
        idx = np.searchsorted(issuances, (t - horizon).to_numpy(), side="right") - 1
        valid = idx >= 0
        chosen = pd.Series(pd.NaT, index=fl.index)
        chosen[valid] = issuances[idx[valid]]
        tmp = fl.assign(_issue=chosen, _t=t)
        merged = tmp.reset_index().merge(
            periods, left_on="_issue", right_on="issue_ts", how="inner"
        )
        covering = merged[
            (merged["fx_start"] <= merged["_t"]) & (merged["_t"] < merged["fx_end"])
        ]
        if covering.empty:
            continue
        sev = covering.groupby("index")["severity"].max()
        result.loc[sev.index] = sev.values
    return result


# ─── 4. FAA Aircraft Registry ────────────────────────────────────────────────

def _normalize_model(mfr: str, model: str) -> str | None:
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
        if pd.notna(row.year_built) and 1950 < row.year_built <= 2025:
            entry["year_built"] = int(row.year_built)
        if pd.notna(row.seats) and row.seats >= 50:
            entry["seats"] = int(row.seats)
        model = _normalize_model(str(row.MFR or ""), str(row.MODEL or ""))
        if model:
            entry["model"] = model
        if entry:
            registry[row.tail] = entry
    print(f"  registry: {len(registry):,} tails")
    return registry


# ─── 5–6. T-100 + DB1B (unchanged logic) ─────────────────────────────────────

def load_t100() -> dict[str, dict]:
    zpath = next(iter(glob.glob(str(T100_DIR / "*.zip"))), None)
    if not zpath:
        raise FileNotFoundError(f"No T-100 zip in {T100_DIR}")
    usecols = ["DEPARTURES_PERFORMED", "SEATS", "PASSENGERS", "ORIGIN", "DEST",
               "YEAR", "MONTH", "CLASS"]
    t100 = pd.read_csv(zpath, usecols=usecols, low_memory=False)
    t100 = t100[
        (t100["CLASS"] == "F") & (t100["SEATS"] > 0)
        & (t100["DEPARTURES_PERFORMED"] > 0)
        & (t100["ORIGIN"].isin(STUDY_AIRPORTS) | t100["DEST"].isin(STUDY_AIRPORTS))
    ]
    grouped = t100.groupby(["ORIGIN", "DEST"]).agg(
        seats=("SEATS", "sum"), pax=("PASSENGERS", "sum"),
        deps=("DEPARTURES_PERFORMED", "sum"),
    )
    route_stats = {
        f"{o}_{d}": {
            "load_factor": round(min(1.0, r.pax / r.seats), 3),
            "avg_seats": round(r.seats / r.deps, 1),
        }
        for (o, d), r in grouped.iterrows()
    }
    print(f"  T-100: {len(route_stats):,} routes")
    return route_stats


def load_db1b() -> dict[str, dict]:
    zpath = next(iter(glob.glob(str(DB1B_DIR / "*.zip"))), None)
    if not zpath:
        raise FileNotFoundError(f"No DB1B zip in {DB1B_DIR}")
    stats = {ap: {"connecting": 0.0, "origin": 0.0, "terminating": 0.0}
             for ap in STUDY_AIRPORTS}
    with zipfile.ZipFile(zpath) as z:
        with z.open(z.namelist()[0]) as f:
            for raw in f:
                parts = raw.decode("ascii", "replace").rstrip("\n").split("|")
                if len(parts) < 21 or (len(parts) - 10) % 11 != 0:
                    continue
                try:
                    n_coupons = int(parts[3])
                    pax = float(parts[4])
                except ValueError:
                    continue
                if parts[5] in stats:
                    stats[parts[5]]["origin"] += pax
                for k in range(n_coupons):
                    base = 10 + 11 * k
                    if base + 7 >= len(parts):
                        break
                    dest = parts[base + 6]
                    if dest in stats:
                        if parts[base + 7].strip() == "" and k < n_coupons - 1:
                            stats[dest]["connecting"] += pax
                        else:
                            stats[dest]["terminating"] += pax
    result = {}
    for ap, s in stats.items():
        local = s["origin"] + s["terminating"]
        total = local + s["connecting"]
        result[ap] = {
            "connection_rate": round(s["connecting"] / total, 3) if total else 0.30,
            "source": "DB1B 2024Q1 (10% ticket sample)",
        }
        print(f"  DB1B {ap}: connection rate {result[ap]['connection_rate']:.1%}")
    return result


# ─── Feature engineering ─────────────────────────────────────────────────────

def _hhmm_to_minutes(series: pd.Series) -> pd.Series:
    v = pd.to_numeric(series, errors="coerce").fillna(0).astype(int)
    return ((v // 100) % 24) * 60 + (v % 100)


def add_network_state(df: pd.DataFrame) -> pd.DataFrame:
    """Trailing-window airport state + inbound tail delay.

    STRICT CAUSALITY: a flight's window contains only flights whose ACTUAL
    departure (scheduled + DepDelayMinutes) is strictly before this flight's
    scheduled departure. DepDelayMinutes ≥ 0 in BTS, so actual ≥ scheduled
    for every flight, and with a strict '<' comparison a row can never see
    its own outcome. Cancelled flights never depart and are excluded.
    """
    df = df.sort_values(["Origin", "sched_dep_ts"]).reset_index(drop=True)
    n = len(df)
    mean2 = np.full(n, np.nan)
    mean4 = np.full(n, np.nan)
    share2 = np.full(n, np.nan)

    two_h = np.timedelta64(2, "h")
    four_h = np.timedelta64(4, "h")

    for _, grp_idx in df.groupby("Origin").indices.items():
        g = df.iloc[grp_idx]
        dep_delay = g["DepDelayMinutes"].to_numpy()
        departed = ~np.isnan(dep_delay)  # cancelled rows have NaN dep delay
        ev_ts = (g["sched_dep_ts"].to_numpy()
                 + dep_delay.astype("timedelta64[m]", copy=False)
                 if False else
                 g["sched_dep_ts"].to_numpy()[departed]
                 + np.array(dep_delay[departed], dtype="timedelta64[m]"))
        ev_delay = dep_delay[departed]
        order = np.argsort(ev_ts, kind="stable")
        ev_ts = ev_ts[order]
        ev_delay = ev_delay[order]
        cum_sum = np.concatenate([[0.0], np.cumsum(ev_delay)])
        cum_late = np.concatenate(
            [[0.0], np.cumsum((ev_delay > DELAY_THRESHOLD_MINUTES).astype(float))]
        )

        t = g["sched_dep_ts"].to_numpy()
        hi = np.searchsorted(ev_ts, t, side="left")     # strictly before t
        lo2 = np.searchsorted(ev_ts, t - two_h, side="left")
        lo4 = np.searchsorted(ev_ts, t - four_h, side="left")

        cnt2 = hi - lo2
        cnt4 = hi - lo4
        with np.errstate(invalid="ignore", divide="ignore"):
            m2 = np.where(cnt2 > 0, (cum_sum[hi] - cum_sum[lo2]) / cnt2, np.nan)
            m4 = np.where(cnt4 > 0, (cum_sum[hi] - cum_sum[lo4]) / cnt4, np.nan)
            s2 = np.where(cnt2 > 0, (cum_late[hi] - cum_late[lo2]) / cnt2, np.nan)
        mean2[grp_idx] = m2
        mean4[grp_idx] = m4
        share2[grp_idx] = s2

    df["trailing_2h_airport_mean_delay"] = np.round(mean2, 2)
    df["trailing_4h_airport_mean_delay"] = np.round(mean4, 2)
    df["trailing_2h_delayed_flight_share"] = np.round(share2, 3)

    # Inbound tail delay: previous leg's ArrDelayMinutes for this tail today.
    # 0 for the first leg of the day (per spec). Note: for extremely late
    # inbounds the final ArrDelay may only be fully known slightly after this
    # leg's scheduled departure — a standard, disclosed approximation.
    df = df.sort_values(["Tail_Number", "FlightDate", "dep_minute_of_day"])
    df["inbound_tail_delay"] = (
        df.groupby(["Tail_Number", "FlightDate"])["ArrDelayMinutes"]
        .shift(1)
        .fillna(0.0)
    )
    return df


def build_features(ontime: pd.DataFrame, weather_hourly: pd.DataFrame,
                   taf_periods: pd.DataFrame, registry: dict,
                   route_stats: dict) -> pd.DataFrame:
    df = ontime.copy()
    df = df[(df["Cancelled"] != 1) & (df["Diverted"] != 1)]
    df = df.dropna(subset=["ArrDelayMinutes", "Tail_Number"])

    # Labels (post-hoc — never same-row features)
    df["label_delayed"] = (df["ArrDelayMinutes"] > DELAY_THRESHOLD_MINUTES).astype(int)
    df["label_delay_minutes"] = df["ArrDelayMinutes"].clip(lower=0)

    dep_min = _hhmm_to_minutes(df["CRSDepTime"])
    arr_min = _hhmm_to_minutes(df["CRSArrTime"])
    df["dep_minute_of_day"] = dep_min
    df["hour_of_day"] = dep_min / 60.0
    df["day_of_week"] = df["FlightDate"].dt.weekday.astype(float)
    df["month"] = df["FlightDate"].dt.month.astype(float)
    df["sched_dep_ts"] = df["FlightDate"] + pd.to_timedelta(dep_min, unit="m")
    df["dep_hour_ts"] = df["FlightDate"] + pd.to_timedelta(dep_min // 60, unit="h")
    df["arr_hour_ts"] = df["FlightDate"] + pd.to_timedelta(arr_min // 60, unit="h")
    df["sched_arr_ts"] = df["FlightDate"] + pd.to_timedelta(arr_min, unit="m")

    # Calendar features
    df["is_federal_holiday"] = df["FlightDate"].isin(HOLIDAY_DATES).astype(float)
    hol_ns = HOLIDAY_DATES.to_numpy()
    dates_ns = df["FlightDate"].to_numpy()
    pos = np.searchsorted(hol_ns, dates_ns)
    prev_gap = (dates_ns - hol_ns[np.clip(pos - 1, 0, len(hol_ns) - 1)])
    next_gap = (hol_ns[np.clip(pos, 0, len(hol_ns) - 1)] - dates_ns)
    days_prev = prev_gap.astype("timedelta64[D]").astype(float)
    days_next = next_gap.astype("timedelta64[D]").astype(float)
    df["days_to_nearest_holiday"] = np.minimum(
        np.abs(days_prev), np.abs(days_next)
    ).clip(0, 60)

    # Rotation features
    df = df.sort_values(["Tail_Number", "FlightDate", "dep_minute_of_day"])
    grp = df.groupby(["Tail_Number", "FlightDate"], sort=False)
    df["rotation_position"] = grp.cumcount() + 1.0
    df["downstream_legs_today"] = (
        grp["Tail_Number"].transform("size") - df["rotation_position"]
    )
    prev_arr = grp["CRSArrTime"].shift(1)
    prev_arr_min = _hhmm_to_minutes(prev_arr)
    gap = df["dep_minute_of_day"] - prev_arr_min
    gap[prev_arr.isna() | (gap < 0) | (gap > 720)] = np.nan
    tail_model = df["Tail_Number"].map(lambda t: registry.get(t, {}).get("model"))
    min_turn = tail_model.map(
        lambda m: TURNAROUND_MAP.get(m, DEFAULT_TURNAROUND)
    ).astype(float)
    df["schedule_slack_minutes"] = (gap - min_turn).fillna(30.0)

    # Registry features (age computed against the flight's own year — a 2019
    # flight must not see the aircraft's 2024 age)
    year_built = df["Tail_Number"].map(
        lambda t: registry.get(t, {}).get("year_built", np.nan)
    )
    df["aircraft_age_years"] = (df["FlightDate"].dt.year - year_built).clip(0, 60)
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

    # ── Network-state features (strictly causal rolling windows) ─────────────
    df = add_network_state(df)

    # ── Weather: TAF forecast first, observed METAR fallback, NaN otherwise ──
    wx = weather_hourly.rename(columns={"hour": "ts"})
    df = df.merge(
        wx.rename(columns={"airport": "Origin", "ts": "dep_hour_ts",
                           "weather_severity": "origin_metar_severity"}),
        on=["Origin", "dep_hour_ts"], how="left",
    )
    df = df.merge(
        wx.rename(columns={"airport": "Dest", "ts": "arr_hour_ts",
                           "weather_severity": "dest_metar_severity"}),
        on=["Dest", "arr_hour_ts"], how="left",
    )
    print("  joining TAF forecasts (≥2h horizon)…")
    origin_taf = join_taf_severity(df, taf_periods, "Origin", "sched_dep_ts")
    dest_taf = join_taf_severity(df, taf_periods, "Dest", "sched_arr_ts")

    df["origin_weather_severity"] = origin_taf.fillna(df["origin_metar_severity"])
    df["dest_weather_severity"] = dest_taf.fillna(df["dest_metar_severity"])
    # NO imputation for airports without weather data: NaN routes natively in
    # LightGBM, and availability itself is a feature.
    df["weather_is_forecast"] = (
        origin_taf.notna() | dest_taf.notna()
    ).astype(float)
    df["weather_data_available"] = (
        df["origin_weather_severity"].notna() | df["dest_weather_severity"].notna()
    ).astype(float)
    n_taf = int(df["weather_is_forecast"].sum())
    print(f"  weather source: TAF forecast {n_taf:,} rows, "
          f"observed METAR {int((df['weather_data_available'] == 1).sum()) - n_taf:,}, "
          f"missing {int((df['weather_data_available'] == 0).sum()):,}")

    # Congestion count inputs (normalizers fitted train-only in split step)
    dep_counts = df.groupby(["Origin", "dep_hour_ts"]).size().rename("dep_count")
    df = df.merge(dep_counts, on=["Origin", "dep_hour_ts"], how="left")
    arr_counts = df.groupby(["Dest", "arr_hour_ts"]).size().rename("arr_count")
    df = df.merge(arr_counts, on=["Dest", "arr_hour_ts"], how="left")
    return df


def split_and_aggregate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame,
                                                   pd.DataFrame, dict]:
    """Time-based three-way split + TRAIN-ONLY fitted constants."""
    year = df["FlightDate"].dt.year
    month = df["FlightDate"].dt.month
    train_mask = year.isin({2019, 2023}) | (
        (year == TEST_YEAR) & (~month.isin(TEST_MONTHS))
    )
    test_mask = (year == TEST_YEAR) & month.isin(TEST_MONTHS)
    oot_mask = year == OOT_YEAR

    train = df[train_mask].copy()
    test = df[test_mask].copy()
    oot = df[oot_mask].copy()
    print(f"  split: train={len(train):,} (2019+2023+2024-01..05), "
          f"test={len(test):,} (2024-06..07), oot_2025={len(oot):,}")

    route_avg = (
        train.groupby(["Origin", "Dest"])["label_delay_minutes"].mean().round(2)
    )
    carrier_otp = (
        (1 - train.groupby("Reporting_Airline")["label_delayed"].mean()).round(3)
    )
    route_map = {f"{o}_{d}": float(v) for (o, d), v in route_avg.items()}
    carrier_map = {c: {"ontime_pct": float(v)} for c, v in carrier_otp.items()}

    dep_p95 = train.groupby("Origin")["dep_count"].quantile(0.95).clip(lower=1)
    arr_p95 = train.groupby("Dest")["arr_count"].quantile(0.95).clip(lower=1)
    dep_global = max(float(train["dep_count"].quantile(0.95)), 1.0)
    arr_global = max(float(train["arr_count"].quantile(0.95)), 1.0)
    dep_p95_map = {k: float(v) for k, v in dep_p95.items()}
    arr_p95_map = {k: float(v) for k, v in arr_p95.items()}

    # Categorical level lists — fitted on TRAIN; unseen levels code to -1,
    # which LightGBM treats as missing for categorical features.
    levels = {
        "carrier": sorted(train["Reporting_Airline"].dropna().unique().tolist()),
        "origin_airport": sorted(train["Origin"].dropna().unique().tolist()),
        "dest_airport": sorted(train["Dest"].dropna().unique().tolist()),
    }
    code_maps = {k: {v: i for i, v in enumerate(vs)} for k, vs in levels.items()}
    source_col = {"carrier": "Reporting_Airline",
                  "origin_airport": "Origin", "dest_airport": "Dest"}

    for frame in (train, test, oot):
        if frame.empty:
            continue
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
        for feat in CATEGORICAL_FEATURES:
            frame[feat] = (
                frame[source_col[feat]].map(code_maps[feat]).fillna(-1).astype(int)
            )

    lookups = {
        "route_averages": route_map,
        "carrier_stats": carrier_map,
        "congestion_p95": {
            "departures_per_hour": dep_p95_map,
            "arrivals_per_hour": arr_p95_map,
            "global_departures": dep_global,
            "global_arrivals": arr_global,
        },
        "categorical_levels": levels,
    }
    return train, test, oot, lookups


# ─── Orchestration ───────────────────────────────────────────────────────────

def run() -> dict:
    print("[1/7] BTS On-Time Performance (2019, 2023, 2024, 2025; COVID skipped)…")
    ontime = load_ontime()
    print("[2/7] NOAA/IEM METAR (observed)…")
    weather = load_metar()
    print("[3/7] NOAA/IEM TAF (forecast)…")
    taf_periods = load_taf()
    print("[4/7] FAA aircraft registry…")
    registry = load_faa_registry()
    print("[5/7] BTS T-100 segment…")
    route_stats = load_t100()
    print("[6/7] BTS DB1B O&D survey…")
    connection_rates = load_db1b()
    print("[7/7] Feature engineering + three-way time split…")
    df = build_features(ontime, weather, taf_periods, registry, route_stats)
    train, test, oot, aggregates = split_and_aggregate(df)

    for col in LEAKY_COLUMNS:
        assert col not in FEATURE_NAMES, f"Label leakage: {col} in features!"
    missing = [f for f in FEATURE_NAMES if f not in train.columns]
    assert not missing, f"Missing engineered features: {missing}"

    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    keep = FEATURE_NAMES + ["label_delayed", "label_delay_minutes", "FlightDate"]
    outputs = {}
    for name, frame in [("train", train), ("test", test), ("oot_2025", oot)]:
        path = PROCESSED_DATA_DIR / f"{name}.parquet"
        if frame.empty:
            print(f"  {name}: EMPTY — skipped (check raw data folder)")
            continue
        frame[keep].to_parquet(path, index=False)
        outputs[name] = path

    study_tails = set(df["Tail_Number"].unique())
    lookups = {
        **aggregates,
        "aircraft_registry": {
            t: {k: v for k, v in registry[t].items()}
            for t in study_tails if t in registry
        },
        "route_stats_t100": route_stats,
        "connection_rates_db1b": connection_rates,
    }
    # age_years for inference-time lookups (age as of the current era)
    for entry in lookups["aircraft_registry"].values():
        if "year_built" in entry:
            entry["age_years"] = round(2024 - entry["year_built"], 1)
    LOOKUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOOKUPS_PATH, "w") as fp:
        json.dump(lookups, fp)

    print(f"  wrote {', '.join(str(p.name) for p in outputs.values())} + lookups.json")
    print(f"  delayed>15min base rates: train {train['label_delayed'].mean():.3f}, "
          f"test {test['label_delayed'].mean():.3f}"
          + (f", oot_2025 {oot['label_delayed'].mean():.3f}" if len(oot) else ""))
    return outputs


if __name__ == "__main__":
    run()
