// Right panel: the AI's top recommended action with rationale, expected
// impact, feasibility checks, and cost comparison.
import type { TimedEvent } from "../../hooks/useSimulation";
import type { RankedOption } from "../../types/recommendations";
import CostBreakdown from "../shared/CostBreakdown";
import { formatCost, formatMinutes, formatPct } from "../../utils/formatting";

interface Props {
  recommendation: TimedEvent | null;
  cascade: TimedEvent | null;
}

export default function AIRecommendation({ recommendation, cascade }: Props) {
  if (!recommendation) {
    return (
      <div className="aero-card h-full flex flex-col">
        <div className="panel-header">
          <span className="panel-title">AI recommendation</span>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-aero-muted text-center px-6">
          <span className="text-2xl opacity-40">◎</span>
          <span className="text-xs leading-relaxed">
            The MILP optimizer engages when a disruption cascade is detected
          </span>
        </div>
      </div>
    );
  }

  const top = recommendation.details.ranked_options?.[0] as RankedOption | undefined;
  if (!top) return null;
  // Compare expected cost to expected baseline (both quadrature-weighted)
  const baseline =
    recommendation.details.evaluation?.expected_baseline_cost ??
    cascade?.details.expected_baseline_cost ??
    cascade?.details.baseline_cost ??
    top.expected_cost;

  return (
    <div className="aero-card h-full flex flex-col border-l-2 border-l-aero-blue overflow-hidden animate-slide-in">
      <div className="panel-header bg-blue-500/[0.06]">
        <span className="text-aero-blue text-xs">◎</span>
        <span className="panel-title text-blue-300">AI recommendation</span>
        <span className="ml-auto font-mono text-[9px] text-aero-muted">
          {recommendation.details.recommendation_id}
        </span>
      </div>
      <div className="p-3 flex flex-col gap-3 overflow-y-auto">
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
          <div className="text-[9px] uppercase text-aero-muted">expected cost cut</div>
        </div>
        <div className="bg-aero-bg rounded p-1.5">
          <div className="font-mono font-bold text-aero-green">
            {formatMinutes(top.delay_impact_minutes)}
          </div>
          <div className="text-[9px] uppercase text-aero-muted">delay impact</div>
        </div>
        <div
          className="bg-aero-bg rounded p-1.5"
          title="Cost if the delay lands in the tail (P90) of the predicted distribution — feasibility is checked at this worst case"
        >
          <div className="font-mono font-bold text-aero-amber">
            {formatCost(top.expected_cost_p90)}
          </div>
          <div className="text-[9px] uppercase text-aero-muted">p90 worst case</div>
        </div>
      </div>

      <CostBreakdown baseline={baseline} optionCost={top.expected_cost} />
      <div
        className="text-[10px] text-aero-muted font-mono flex justify-between"
        title="Each action is costed at the P10, P50 and P90 predicted delays; options are ranked by the 0.25/0.50/0.25 weighted expected cost"
      >
        <span>E[cost] over delay distribution</span>
        <span>
          {formatCost(top.expected_cost_p10)} · {formatCost(top.expected_cost_p50)} ·{" "}
          {formatCost(top.expected_cost_p90)}
        </span>
      </div>

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
    </div>
  );
}
