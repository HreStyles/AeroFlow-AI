// Method 3 — 4-strategy baseline comparison bar chart (SVG): the MILP
// recommendation must beat do-nothing, random-feasible, and greedy.
import { formatCost } from "../../utils/formatting";

interface Props {
  costs: Record<string, number>; // {do_nothing, random, greedy, milp}
}

const STRATEGY_META: Record<string, { label: string; color: string }> = {
  do_nothing: { label: "Do nothing", color: "#ef4444" },
  random: { label: "Random feasible", color: "#f59e0b" },
  greedy: { label: "Greedy heuristic", color: "#3b82f6" },
  milp: { label: "MILP (AeroFlow)", color: "#22c55e" },
};

export default function BaselineComparison({ costs }: Props) {
  const entries = Object.keys(STRATEGY_META)
    .filter((k) => k in costs)
    .map((k) => ({ key: k, ...STRATEGY_META[k], value: costs[k] }));
  const max = Math.max(...entries.map((e) => e.value), 1);
  const W = 480;
  const H = 40 * entries.length + 10;
  const labelW = 130;

  return (
    <div className="aero-card p-4">
      <div className="aero-label mb-2">Method 3 · strategy comparison (total disruption cost)</div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {entries.map((e, i) => {
          const y = i * 40 + 8;
          const barW = Math.max(2, (e.value / max) * (W - labelW - 90));
          return (
            <g key={e.key}>
              <text x={0} y={y + 14} fontSize={11} fill="#94a3b8">
                {e.label}
              </text>
              <rect
                x={labelW}
                y={y}
                width={barW}
                height={20}
                rx={3}
                fill={e.color}
                opacity={0.85}
              />
              <text
                x={labelW + barW + 6}
                y={y + 14}
                fontSize={11}
                fill="#e2e8f0"
                className="font-mono"
              >
                {formatCost(e.value)}
              </text>
            </g>
          );
        })}
      </svg>
      {costs.do_nothing > 0 && costs.milp !== undefined && (
        <div className="text-xs text-aero-green mt-1">
          MILP reduces disruption cost by{" "}
          {(((costs.do_nothing - costs.milp) / costs.do_nothing) * 100).toFixed(1)}% vs
          doing nothing.
        </div>
      )}
    </div>
  );
}
