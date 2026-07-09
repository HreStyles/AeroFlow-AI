// Bottom-center: ranked options comparison table.
import type { TimedEvent } from "../../hooks/useSimulation";
import type { RankedOption } from "../../types/recommendations";
import { formatCost, formatMinutes, formatPct } from "../../utils/formatting";

interface Props {
  recommendation: TimedEvent | null;
  selectedRank: number | null;
  onSelectRank: (rank: number) => void;
}

const IMPACT_COLOR = {
  low: "text-aero-green",
  medium: "text-aero-amber",
  high: "text-aero-red",
};

export default function OptionsTable({
  recommendation,
  selectedRank,
  onSelectRank,
}: Props) {
  const options = (recommendation?.details.ranked_options ?? []) as RankedOption[];

  return (
    <div className="aero-card p-3 h-full flex flex-col min-h-0">
      <span className="aero-label mb-2">AI options — ranked comparison</span>
      {options.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-aero-muted text-xs">
          No options generated yet
        </div>
      ) : (
        <div className="overflow-auto min-h-0">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-left text-aero-muted uppercase text-[9px] tracking-wider">
                <th className="py-1 pr-2">#</th>
                <th className="py-1 pr-2">Action</th>
                <th className="py-1 pr-2 text-right">Cost</th>
                <th className="py-1 pr-2 text-right">Reduction</th>
                <th className="py-1 pr-2 text-right">Delay Δ</th>
                <th className="py-1 pr-2">Downstream</th>
                <th className="py-1 pr-2 text-right">Success</th>
              </tr>
            </thead>
            <tbody>
              {options.map((o) => (
                <tr
                  key={o.rank}
                  onClick={() => onSelectRank(o.rank)}
                  className={`border-t border-aero-border cursor-pointer transition-colors ${
                    selectedRank === o.rank
                      ? "bg-aero-blue/15"
                      : "hover:bg-aero-border/30"
                  }`}
                >
                  <td className="py-1.5 pr-2 font-mono">
                    {o.rank === 1 ? (
                      <span className="text-aero-blue font-bold">★1</span>
                    ) : (
                      o.rank
                    )}
                  </td>
                  <td className="py-1.5 pr-2 max-w-[320px] truncate" title={o.action}>
                    {o.action}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono">
                    {formatCost(o.expected_cost)}
                  </td>
                  <td
                    className={`py-1.5 pr-2 text-right font-mono ${
                      o.cost_reduction_pct > 0 ? "text-aero-green" : "text-aero-muted"
                    }`}
                  >
                    {formatPct(o.cost_reduction_pct)}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono">
                    {formatMinutes(o.delay_impact_minutes)}
                  </td>
                  <td className={`py-1.5 pr-2 ${IMPACT_COLOR[o.downstream_impact] ?? ""}`}>
                    {o.downstream_impact}
                  </td>
                  <td className="py-1.5 pr-2 text-right font-mono">
                    {Math.round(o.success_probability * 100)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
