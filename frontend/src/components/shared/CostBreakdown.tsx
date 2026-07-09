// Horizontal stacked cost visualization comparing baseline vs an option.
import { formatCost } from "../../utils/formatting";

interface Props {
  baseline: number;
  optionCost: number;
  optionLabel?: string;
}

export default function CostBreakdown({ baseline, optionCost, optionLabel }: Props) {
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
    </div>
  );
}
