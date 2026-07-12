// Horizontal stacked cost visualization comparing baseline vs an option,
// with the cost model's per-weight derivations surfaced on hover — every
// dollar figure traces back to a cited source, never an arbitrary constant.
import { formatCost } from "../../utils/formatting";
import type { CostModel } from "../../types/scenario";

interface Props {
  baseline: number;
  optionCost: number;
  optionLabel?: string;
  costModel?: CostModel;
}

const WEIGHT_LABELS: Record<string, string> = {
  passenger_delay_per_minute: "Passenger delay ($/pax·min)",
  aircraft_operating_cost_per_minute: "Aircraft operating ($/min)",
  missed_connection_per_pax: "Missed connection ($/pax)",
  crew_overtime_per_hour: "Crew overtime ($/hr)",
  gate_conflict_base: "Gate conflict, base ($)",
  gate_conflict_per_overlap_minute: "Gate conflict ($/overlap·min)",
  aircraft_swap_cost: "Aircraft swap ($)",
  fuel_taxi_per_minute: "Excess taxi ($/min)",
};

export default function CostBreakdown({
  baseline,
  optionCost,
  optionLabel,
  costModel,
}: Props) {
  const max = Math.max(baseline, optionCost, 1);
  const rows = [
    { label: "Do nothing", value: baseline, color: "#ef4444" },
    { label: optionLabel ?? "Recommended", value: optionCost, color: "#22c55e" },
  ];
  return (
    <div className="space-y-1.5">
      {rows.map((row) => (
        <div key={row.label}>
          <div className="flex justify-between text-[11px] mb-0.5">
            <span className="text-aero-muted">{row.label}</span>
            <span className="font-mono">{formatCost(row.value)}</span>
          </div>
          <div className="h-2 rounded bg-aero-bg overflow-hidden">
            <div
              className="h-full rounded transition-all duration-500"
              style={{
                width: `${(row.value / max) * 100}%`,
                backgroundColor: row.color,
              }}
            />
          </div>
        </div>
      ))}
      {baseline > optionCost && (
        <div className="text-[11px] text-aero-green font-medium">
          Saves {formatCost(baseline - optionCost)} (
          {(((baseline - optionCost) / baseline) * 100).toFixed(1)}%)
        </div>
      )}

      {costModel?.weights && (
        <div className="pt-1">
          <div className="aero-label mb-1">
            Cost model {costModel.version ? `· ${costModel.version}` : ""} — hover
            any weight for its derivation
          </div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(costModel.weights).map(([key, value]) => (
              <span
                key={key}
                className="status-chip border-aero-border text-aero-muted bg-aero-bg cursor-help hover:border-aero-blue/60 hover:text-aero-text transition-colors"
                title={`${WEIGHT_LABELS[key] ?? key} = $${value}\n\n${
                  costModel.derivations?.[key] ?? "No derivation recorded"
                }`}
              >
                {(WEIGHT_LABELS[key] ?? key).split(" (")[0]}
                <span className="font-mono">${value}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
