// Left panel: predicted delay, confidence gauge, SHAP factors, cascade impact.
import type { TimedEvent } from "../../hooks/useSimulation";
import type { DelayPrediction, CascadeResult } from "../../types/events";
import ConfidenceGauge from "../shared/ConfidenceGauge";
import ProvenanceBadge from "../shared/ProvenanceBadge";
import { formatCost, probabilityColor } from "../../utils/formatting";

interface Props {
  prediction: TimedEvent | null;
  cascade: TimedEvent | null;
}

export default function DisruptionAlert({ prediction, cascade }: Props) {
  if (!prediction) {
    return (
      <div className="aero-card p-3 h-full flex flex-col">
        <span className="aero-label">Disruption alert</span>
        <div className="flex-1 flex items-center justify-center text-aero-muted text-xs">
          No active delay predictions
        </div>
      </div>
    );
  }

  const p = prediction.details as unknown as DelayPrediction;
  const c = cascade?.details as unknown as CascadeResult | undefined;
  const maxShap = Math.max(
    ...p.shap_factors.map((f) => Math.abs(f.contribution)),
    0.001
  );

  return (
    <div className="aero-card p-3 h-full flex flex-col gap-3 overflow-y-auto border-l-2 border-l-aero-red">
      <div className="flex items-center justify-between">
        <span className="aero-label text-aero-red">⚠ Disruption alert</span>
        <span className="font-mono text-xs text-aero-muted">{prediction.sim_time}</span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1">
          <div className="font-mono font-bold text-xl">{p.flight_id}</div>
          <div className={`text-2xl font-bold font-mono ${probabilityColor(p.probability)}`}>
            {Math.round(p.probability * 100)}%
          </div>
          <div className="aero-label">delay probability</div>
        </div>
        <ConfidenceGauge value={p.confidence} size={68} />
      </div>

      <div>
        <div className="aero-label mb-1">Predicted delay (P10 / P50 / P90)</div>
        <div className="flex gap-2 font-mono text-sm">
          <span className="text-aero-green">{p.p10_minutes}m</span>
          <span className="text-aero-amber font-bold">{p.p50_minutes}m</span>
          <span className="text-aero-red">{p.p90_minutes}m</span>
        </div>
        {/* distribution bar */}
        <div className="relative h-1.5 mt-1 rounded bg-aero-bg">
          <div
            className="absolute h-full rounded bg-gradient-to-r from-aero-green via-aero-amber to-aero-red"
            style={{
              left: `${Math.min(90, (p.p10_minutes / Math.max(p.p90_minutes, 1)) * 100)}%`,
              right: "0%",
            }}
          />
        </div>
      </div>

      <div>
        <div className="aero-label mb-1">Contributing factors (SHAP)</div>
        <div className="space-y-1">
          {p.shap_factors.map((f) => (
            <div key={f.feature} className="flex items-center gap-1.5 text-[11px]">
              <span className="w-32 truncate text-aero-muted" title={f.feature}>
                {f.feature.replace(/_/g, " ")}
              </span>
              <div className="flex-1 h-1.5 bg-aero-bg rounded overflow-hidden">
                <div
                  className={`h-full ${f.contribution >= 0 ? "bg-aero-red" : "bg-aero-green"}`}
                  style={{ width: `${(Math.abs(f.contribution) / maxShap) * 100}%` }}
                />
              </div>
              <span className="font-mono w-11 text-right">
                {f.contribution >= 0 ? "+" : ""}
                {f.contribution.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {c && (
        <div className="border-t border-aero-border pt-2">
          <div className="aero-label mb-1 text-aero-red">Cascade impact</div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
            <span className="text-aero-muted">Affected flights</span>
            <span className="font-mono text-right">
              {c.affected_flights.length}
            </span>
            <span className="text-aero-muted">Gate conflicts</span>
            <span className="font-mono text-right">{c.gate_conflicts.length}</span>
            <span className="text-aero-muted">Missed connections</span>
            <span className="font-mono text-right">{c.missed_connections}</span>
            <span className="text-aero-muted">Downstream delay</span>
            <span className="font-mono text-right">
              {Math.round(c.total_downstream_delay_minutes)} min
            </span>
            <span className="text-aero-muted">Do-nothing cost</span>
            <span className="font-mono text-right text-aero-red">
              {formatCost(c.baseline_cost)}
            </span>
          </div>
        </div>
      )}

      <div className="border-t border-aero-border pt-2">
        <div className="aero-label mb-1">Data provenance</div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(p.provenance ?? {})
            .filter(([, v]) => !v.startsWith("user_provided"))
            .slice(0, 6)
            .map(([field, v]) => (
              <span key={field} className="inline-flex items-center gap-1 text-[10px] text-aero-muted">
                {field.replace(/_/g, " ")}
                <ProvenanceBadge provenance={v} compact />
              </span>
            ))}
        </div>
      </div>
    </div>
  );
}
