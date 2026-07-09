// Method 4 — cost-weight sensitivity: does the recommendation survive ±20%
// perturbations of the cost weights?
import type { SensitivityResult } from "../../types/events";

interface Props {
  sensitivity: SensitivityResult | null;
}

export default function SensitivityHeatmap({ sensitivity }: Props) {
  const stable = sensitivity?.stable_pct ?? null;
  const color =
    stable === null
      ? "text-aero-muted"
      : stable >= 80
        ? "text-aero-green"
        : stable >= 50
          ? "text-aero-amber"
          : "text-aero-red";
  return (
    <div className="aero-card p-4">
      <div className="aero-label mb-2">Method 4 · cost-weight sensitivity</div>
      <div className={`text-4xl font-bold font-mono ${color}`}>
        {stable === null ? "—" : `${stable}%`}
      </div>
      <div className="text-xs text-aero-muted mt-1">
        Recommendation unchanged across {sensitivity?.perturbation ?? "±20% weight perturbations"}.
      </div>
      {sensitivity?.fragile_ranges && sensitivity.fragile_ranges.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="aero-label">Fragile weights</div>
          {sensitivity.fragile_ranges.map((f, i) => (
            <div key={i} className="text-[11px] font-mono text-aero-amber">
              {f.weight} ×{f.factor} → {f.flips_to}
            </div>
          ))}
        </div>
      )}
      {sensitivity?.note && (
        <div className="text-[11px] text-aero-muted mt-2">{sensitivity.note}</div>
      )}
    </div>
  );
}
