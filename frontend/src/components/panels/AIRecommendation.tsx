// Right panel: the AI's top recommended action with rationale, expected
// impact, feasibility checks, and cost comparison.
import type { TimedEvent } from "../../hooks/useSimulation";
import type { RankedOption } from "../../types/recommendations";
import CostBreakdown from "../shared/CostBreakdown";
import { formatMinutes, formatPct } from "../../utils/formatting";

interface Props {
  recommendation: TimedEvent | null;
  cascade: TimedEvent | null;
}

export default function AIRecommendation({ recommendation, cascade }: Props) {
  if (!recommendation) {
    return (
      <div className="aero-card p-3 h-full flex flex-col">
        <span className="aero-label">AI recommendation</span>
        <div className="flex-1 flex items-center justify-center text-aero-muted text-xs text-center px-4">
          Recommendations appear here when a disruption cascade is detected
        </div>
      </div>
    );
  }

  const top = recommendation.details.ranked_options?.[0] as RankedOption | undefined;
  if (!top) return null;
  const baseline = cascade?.details.baseline_cost ?? top.expected_cost;

  return (
    <div className="aero-card p-3 h-full flex flex-col gap-3 overflow-y-auto border-l-2 border-l-aero-blue">
      <div className="flex items-center justify-between">
        <span className="aero-label text-aero-blue">🤖 AI recommendation</span>
        <span className="font-mono text-[10px] text-aero-muted">
          {recommendation.details.recommendation_id}
        </span>
      </div>

      <div>
        <div className="text-[10px] uppercase text-aero-muted mb-0.5">
          Recommended action · rank #1
        </div>
        <div className="text-sm font-medium leading-snug">{top.action}</div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-aero-bg rounded p-1.5">
          <div className="font-mono font-bold text-aero-green">
            {formatPct(top.cost_reduction_pct)}
          </div>
          <div className="text-[9px] uppercase text-aero-muted">cost cut</div>
        </div>
        <div className="bg-aero-bg rounded p-1.5">
          <div className="font-mono font-bold text-aero-green">
            {formatMinutes(top.delay_impact_minutes)}
          </div>
          <div className="text-[9px] uppercase text-aero-muted">delay impact</div>
        </div>
        <div className="bg-aero-bg rounded p-1.5">
          <div className="font-mono font-bold">
            {Math.round(top.success_probability * 100)}%
          </div>
          <div className="text-[9px] uppercase text-aero-muted">success prob</div>
        </div>
      </div>

      <CostBreakdown baseline={baseline} optionCost={top.expected_cost} />

      <div>
        <div className="aero-label mb-1">Rationale</div>
        <ul className="space-y-1">
          {top.rationale.map((r, i) => (
            <li key={i} className="text-[11px] flex gap-1.5">
              <span className="text-aero-blue">▸</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <div className="aero-label mb-1">Feasibility checks</div>
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(top.feasibility_checks).map(([check, ok]) => (
            <span
              key={check}
              className={`text-[10px] px-1.5 py-0.5 rounded border ${
                ok
                  ? "border-green-500/30 text-aero-green bg-green-500/10"
                  : "border-red-500/30 text-aero-red bg-red-500/10"
              }`}
            >
              {ok ? "✓" : "✗"} {check.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      </div>

      <div className="mt-auto pt-1 flex justify-between text-[10px] text-aero-muted font-mono">
        <span>optimality gap {formatPct(top.optimality_gap_pct, 2)}</span>
        <span>
          solved in {(recommendation.details.solver_time_seconds ?? 0).toFixed(2)}s
        </span>
      </div>
    </div>
  );
}
