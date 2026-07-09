// Card grid of preset scenarios. Selecting one runs the live pipeline on the
// backend, then navigates to the simulation dashboard for playback.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import { api } from "../api/client";
import { useScenario } from "../hooks/useScenario";
import type { PresetSummary } from "../types/scenario";

const PRESET_ICONS: Record<string, string> = {
  thunderstorm_atl: "⛈",
  mechanical_cascade_jfk: "🔧",
  gdp_afternoon_rush: "🛑",
};

export default function PresetsPage() {
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [listError, setListError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);
  const { loadPreset, error } = useScenario();
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getPresets()
      .then((r) => setPresets(r.presets))
      .catch((e) => setListError(String(e.message ?? e)));
  }, []);

  const run = async (id: string) => {
    setRunningId(id);
    const log = await loadPreset(id);
    setRunningId(null);
    if (log) navigate("/simulate");
  };

  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto p-6">
        <h1 className="text-xl font-bold mb-1">Preset scenarios</h1>
        <p className="text-sm text-aero-muted mb-6">
          Curated disruption scenarios sourced from the Monte Carlo generator.
          Selecting one runs the full prediction → simulation → optimization
          pipeline live and opens the playback dashboard.
        </p>

        {listError && (
          <div className="rounded border border-red-500/40 bg-red-500/10 text-aero-red text-sm px-4 py-3 mb-4">
            Could not reach the backend: {listError}. Is uvicorn running on port
            8000?
          </div>
        )}
        {error && (
          <div className="rounded border border-red-500/40 bg-red-500/10 text-aero-red text-sm px-4 py-3 mb-4">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {presets.map((p) => (
            <div key={p.id} className="aero-card p-4 flex flex-col gap-3">
              <div className="flex items-start justify-between">
                <span className="text-3xl">{PRESET_ICONS[p.id] ?? "✈️"}</span>
                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-aero-bg border border-aero-border text-aero-muted">
                  {p.airport}
                </span>
              </div>
              <div>
                <h2 className="font-semibold leading-snug">{p.name}</h2>
                <p className="text-xs text-aero-muted mt-1 leading-relaxed">
                  {p.description}
                </p>
              </div>
              <div className="mt-auto flex items-center justify-between">
                <span className="text-[11px] text-aero-muted font-mono">
                  {p.flight_count} flights
                  {p.gdp_event_count > 0 && ` · ${p.gdp_event_count} GDP`}
                </span>
                <button
                  onClick={() => run(p.id)}
                  disabled={runningId !== null}
                  className="aero-btn-primary text-xs"
                  data-testid={`run-${p.id}`}
                >
                  {runningId === p.id ? "Running pipeline…" : "Run scenario"}
                </button>
              </div>
            </div>
          ))}
        </div>

        {presets.length === 0 && !listError && (
          <div className="text-aero-muted text-sm">Loading presets…</div>
        )}
      </div>
    </PageLayout>
  );
}
