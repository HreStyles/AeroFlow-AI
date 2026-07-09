# AeroFlow AI

An AI-powered **Airport Operations Control Center (AOCC) Decision Support System**.
It predicts flight delays, simulates how they cascade through airport operations
(gates, aircraft rotations, crew, passenger connections), and recommends optimized
operational decisions that minimize total disruption — with a human in the loop.

**Three computational components:**

| | Component | Technology | Role |
|---|---|---|---|
| **A** | Prediction | LightGBM + SHAP | Delay probability + P10/P50/P90 duration distribution, confidence score, per-prediction factor attribution |
| **B** | Simulation | Discrete-event engine | Propagates predicted delays through the operational graph: rotation cascades, gate conflicts, missed connections |
| **C** | Optimization | MILP (Google OR-Tools) | Searches gate reassignments, aircraft swaps, and passenger rebooking for the cost-minimizing feasible response, with provable optimality gap |

The frontend is a dark AOCC dashboard (React 18 + TypeScript + Tailwind CSS 3 + Vite)
that plays back the pipeline's timestamped event log with time controls
(play/pause/1–50x/step/jump-to-event) — zero backend calls during playback.

---

## Quick start

### Backend (Python 3.11+, tested on 3.13)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --reload        # http://localhost:8000
```

> **macOS note:** if `import lightgbm` fails with a missing `libomp.dylib` and you
> don't have Homebrew, rebuild it without OpenMP:
> `.venv/bin/pip install --no-binary lightgbm lightgbm -C cmake.define.USE_OPENMP=OFF`

### Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev                                 # http://localhost:5173 (proxies /api → :8000)
```

Open http://localhost:5173, go to **Presets**, and run a scenario.

---

## Untrained vs trained model behavior

The system ships **without** trained model files (they are gitignored):

- **Preset scenarios work immediately** — they run the full live pipeline
  (simulation + MILP optimization are always real) using a clearly-labeled
  heuristic prediction fallback. Every prediction is tagged
  `prediction_source: "heuristic_fallback (model not trained)"` and the
  dashboard shows an amber warning banner.
- **`POST /api/simulate` (custom scenarios) returns 503** with instructions to
  train the model first. There is no mock predictor — custom scenarios only run
  against the real trained LightGBM models.

### Training the real model

```bash
./scripts/download_bts.sh 2024 1 2 3 4 5 6      # BTS On-Time Performance data
./scripts/download_noaa.sh 2024-01-01 2024-07-01 # METAR weather (IEM archive)
backend/.venv/bin/python scripts/train_all.py    # pipeline → classifier → quantiles → eval → SHAP
```

This writes `backend/models/saved/classifier.txt`, `quantile_p{10,50,90}.txt`,
`lookups.json`, `evaluation_report.json`, and `shap_global.json`. Restart uvicorn
and the API serves real predictions (check `GET /api/health` → `model_trained: true`).

Training methodology: time-based train/test split (never random — prevents
temporal leakage), strict temporal-causality feature filtering, class-imbalance
weighting, quantile regression for the delay-duration distribution, calibration
+ pinball-loss evaluation.

---

## Repository layout

```
backend/
  main.py, config.py            FastAPI entry point; all constants/tables/weights
  api/                          routes + Pydantic schemas
  component_a/                  ML predictor (LightGBM + SHAP) + feature engineering
  component_b/                  discrete-event simulation + operational graph + airport models
  component_c/                  MILP optimizer + action generator + cost function + baselines
  pipeline/                     completeness layer (provenance), scenario runner, event log
  generators/                   Monte Carlo scenario generator + synthetic schedules
  models/training/              data pipeline, training, evaluation, explainability
  data/airports/                ATL.json, JFK.json (gates, compat, runways, map layout)
  data/presets/                 3 curated disruption scenarios
frontend/
  src/pages/                    Landing, Simulation, ScenarioBuilder, Presets, Validation
  src/components/               map, panels, scenario-builder forms, validation charts
  src/hooks/                    useSimulation (playback), useScenario, useEventLog
scripts/                        data download, train_all.py, generate_presets.py
```

## API

| Route | Description |
|---|---|
| `GET /api/health` | status + whether trained models are loaded |
| `GET /api/presets` | list preset scenarios |
| `GET /api/presets/{id}` | run the pipeline live on a preset → event log |
| `POST /api/simulate` | run a custom scenario (requires trained model) |
| `POST /api/simulate/{id}/decision` | log operator accept/override (feedback loop) |
| `GET /api/airports/{code}` | airport config (gates, runways, map layout) |
| `GET /api/validation/backtest` | Monte Carlo stress / backtest report |

## Key architectural rules

1. **No hallucinated data** — every field is tagged `user_provided` / `derived` /
   `assumed_default` by the completeness layer; required fields with no safe
   default (e.g. `aircraft_type`) are rejected, never guessed.
2. **The event log is the single source of truth** — the frontend never calls
   the ML model, simulator, or optimizer directly; it plays back a JSON event log.
3. **Cost weights are always configurable** — per-scenario config or documented
   defaults, never hardcoded in the engines.
4. **Validation ships with every run** — MILP optimality gap (Method 1),
   4-strategy baseline comparison (Method 3), and ±20% cost-weight sensitivity
   (Method 4) are computed from real solver/simulation runs per scenario.
