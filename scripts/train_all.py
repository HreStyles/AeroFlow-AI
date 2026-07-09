#!/usr/bin/env python
"""
Full training pipeline:
    data_pipeline → train_classifier → train_quantile → evaluate → explain

Prerequisites: raw data downloaded via scripts/download_bts.sh and
scripts/download_noaa.sh.

Run with the backend venv from the repo root:
    backend/.venv/bin/python scripts/train_all.py
"""
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from models.training import data_pipeline, evaluate, explain  # noqa: E402
from models.training import train_classifier, train_quantile  # noqa: E402


def main():
    t0 = time.time()

    print("=" * 60)
    print("STEP 1/5 — Data pipeline (load, clean, merge, features, split)")
    print("=" * 60)
    data_pipeline.run()

    print("\n" + "=" * 60)
    print("STEP 2/5 — Train delay-probability classifier (LightGBM binary)")
    print("=" * 60)
    train_classifier.train()

    print("\n" + "=" * 60)
    print("STEP 3/5 — Train delay-duration quantile models (α=0.1/0.5/0.9)")
    print("=" * 60)
    train_quantile.train()

    print("\n" + "=" * 60)
    print("STEP 4/5 — Evaluate (AUC, PR-AUC, calibration, pinball loss)")
    print("=" * 60)
    evaluate.evaluate()

    print("\n" + "=" * 60)
    print("STEP 5/5 — Global SHAP feature importance")
    print("=" * 60)
    explain.explain()

    print(f"\n✅ Training pipeline complete in {time.time() - t0:.0f}s.")
    print("The API now serves real model predictions (restart uvicorn if running).")


if __name__ == "__main__":
    main()
