// Left panel: predicted delay, confidence gauge, delay distribution strip,
// SHAP factors, cascade impact.
import type { TimedEvent } from "../../hooks/useSimulation";
import type { DelayPrediction, CascadeResult } from "../../types/events";
import ConfidenceGauge from "../shared/ConfidenceGauge";
import ProvenanceBadge from "../shared/ProvenanceBadge";
import { formatCost, probabilityColor } from "../../utils/formatting";

interface Props {
  prediction: TimedEvent | null;
  cascade: TimedEvent | null;
}

function DistributionStrip({ p }: { p: DelayPrediction }) {
  const max = Math.max(p.p90_minutes * 1.15, 30);
  const x = (v: number) => (v / max) * 100;
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="aero-label">Predicted delay distribution</span>
        <span className="text-[10px] font-mono text-aero-muted">min</span>
      </div>
      <svg viewBox="0 0 100 26" preserveAspectRatio="none" className="w-full h-10">
        <line x1="0" y1="13" x2="100" y2="13" stroke="#1e293b" strokeWidth="1" />
        {/* P10–P90 band */}
        <rect
          x={x(p.p10_minutes)} y="9"
          width={Math.max(x(p.p90_minutes) - x(p.p10_minutes), 1)} height="8"
          rx="2" fill="url(#dist-grad)" opacity="0.85"
        />
        <defs>
          <linearGradient id="dist-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#22c55e" />
            <stop offset="55%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>
        {/* median marker */}
        <line x1={x(p.p50_minutes)} y1="5" x2={x(p.p50_minutes)} y2="21"
          stroke="#e2e8f0" strokeWidth="1.4" />
      </svg>
      <div className="relative h-4 text-[10px] font-mono">
        <span className="absolute text-aero-green" style={{ left: `${x(p.p10_minutes)}%`, transform: "translateX(-50%)" }}>
          {p.p10_minutes}
        </span>
        <span className="absolute font-bold text-aero-text" style={{ left: `${x(p.p50_minutes)}%`, transform: "translateX(-50%)" }}>
          {p.p50_minutes}
        </span>
        <span className="absolute text-aero-red" style={{ left: `${x(p.p90_minutes)}%`, transform: "translateX(-50%)" }}>
          {p.p90_minutes}
        </span>
      </div>
      <div className="flex justify-between text-[9px] uppercase tracking-wider text-aero-muted">
        <span>P10 optimistic</span>
        <span>P50 median</span>
        <span>P90 tail risk</span>
      </div>
    </div>
  );
}

export default function DisruptionAlert({ prediction, cascade }: Props) {
  if (!prediction) {
    return (
      <div className="aero-card h-full flex flex-col">
        <div className="panel-header">
          <span className="panel-title">Disruption alert</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-aero-muted">
          <span className="text-2xl opacity-40">☰</span>
          <span className="text-xs">Monitoring — no active delay predictions</span>
        </div>
      </div>
    );
  }

  const p = prediction.details as unknown as DelayPrediction;
  const c = cascade?.details as unknown as CascadeResult | undefined;
  const maxShap = Math.max(...p.shap_factors.map((f) => Math.abs(f.contribution)), 0.001);

  return (
    <div className="aero-card h-full flex flex-col border-l-2 border-l-aero-red overflow-hidden animate-slide-in">
      <div className="panel-header bg-red-500/[0.06]">
        <span className="text-aero-red text-xs animate-pulse-alert">⚠</span>
        <span className="panel-title text-red-300">Disruption alert</span>
        <span className="ml-auto font-mono text-[10px] text-aero-muted">{prediction.sim_time}</span>
      </div>

      <div className="p-3 flex flex-col gap-3 overflow-y-auto">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="font-mono font-bold text-2xl leading-none">{p.flight_id}</div>
            <div className={`text-3xl font-bold font-mono mt-1 ${probabilityColor(p.probability)}`}>
              {Math.round(p.probability * 100)}
              <span className="text-lg">%</span>
            </div>
            <div className="aero-label">delay probability</div>
          </div>
          <ConfidenceGauge value={p.confidence} size={72} />
        </div>

        <DistributionStrip p={p} />

        <div>
          <div className="aero-label mb-1.5">Contributing factors · SHAP</div>
          <div className="space-y-1.5">
            {p.shap_factors.map((f) => (
              <div key={f.feature} className="flex items-center gap-2 text-[11px]">
                <span className="w-[118px] truncate text-slate-400" title={f.feature}>
                  {f.feature.replace(/_/g, " ")}
                </span>
                <div className="flex-1 h-2 bg-aero-bg rounded-sm overflow-hidden">
                  <div
                    className={`h-full rounded-sm ${f.contribution >= 0 ? "bg-aero-red" : "bg-aero-green"}`}
                    style={{ width: `${(Math.abs(f.contribution) / maxShap) * 100}%` }}
                  />
                </div>
                <span className={`font-mono w-12 text-right ${f.contribution >= 0 ? "text-red-300" : "text-green-300"}`}>
                  {f.contribution >= 0 ? "+" : ""}
                  {f.contribution.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-1 text-[9px] text-aero-muted">
            <span><span className="text-aero-red">■</span> raises risk</span>
            <span><span className="text-aero-green">■</span> lowers risk</span>
          </div>
        </div>

        {c && (
          <div>
            <div className="aero-label mb-1.5 text-red-300">Cascade impact · simulated</div>
            <div className="grid grid-cols-2 gap-1.5">
              <div className="stat-tile">
                <div className="font-mono font-bold text-sm">{c.affected_flights.length}</div>
                <div className="text-[9px] uppercase text-aero-muted">downstream flights</div>
              </div>
              <div className="stat-tile">
                <div className="font-mono font-bold text-sm">{c.gate_conflicts.length}</div>
                <div className="text-[9px] uppercase text-aero-muted">gate conflicts</div>
              </div>
              <div className="stat-tile">
                <div className={`font-mono font-bold text-sm ${c.missed_connections ? "text-aero-red" : ""}`}>
                  {c.missed_connections}
                </div>
                <div className="text-[9px] uppercase text-aero-muted">missed connections</div>
              </div>
              <div className="stat-tile">
                <div className="font-mono font-bold text-sm text-aero-red">
                  {formatCost(c.baseline_cost)}
                </div>
                <div className="text-[9px] uppercase text-aero-muted">do-nothing cost</div>
              </div>
            </div>
          </div>
        )}

        <div className="border-t border-aero-border/60 pt-2">
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
    </div>
  );
}
