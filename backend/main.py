"""
AeroFlow AI — FastAPI application entry point.

Run from the backend/ directory:
    uvicorn main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router

app = FastAPI(
    title="AeroFlow AI",
    description=(
        "AI-powered Airport Operations Control Center decision support: "
        "delay prediction (LightGBM) → cascade simulation (discrete-event) → "
        "response optimization (MILP via OR-Tools)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    """The backend serves JSON only — the dashboard UI is the frontend dev
    server (npm run dev → http://localhost:5173)."""
    return {
        "service": "AeroFlow AI backend",
        "ui": "http://localhost:5173 (run `npm run dev` in frontend/)",
        "api_docs": "/docs",
        "health": "/api/health",
        "presets": "/api/presets",
    }
