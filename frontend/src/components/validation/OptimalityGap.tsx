// Method 1 — MILP optimality gap: distance between the found solution and
// the solver's proven lower bound. Near 0% ⇒ provably (near-)optimal.
interface Props {
  gapPct: number | null;
}

export default function OptimalityGap({ gapPct }: Props) {
  const gap = gapPct ?? 0;
  const quality =
    gap <= 1 ? "provably near-optimal" : gap <= 5 ? "strong solution" : "heuristic-grade";
  const color = gap <= 1 ? "text-aero-green" : gap <= 5 ? "text-aero-amber" : "text-aero-red";
  return (
    <div className="aero-card p-4">
      <div className="aero-label mb-2">Method 1 · MILP optimality gap</div>
      <div className={`text-4xl font-bold font-mono ${color}`}>
        {gap.toFixed(2)}%
      </div>
      <div className="text-xs text-aero-muted mt-1">
        Gap between the recommended solution's cost and the solver's proven
        bound — <span className={color}>{quality}</span>.
      </div>
    </div>
  );
}
