// Method 5 — component ablation: what breaks when each layer is removed.
// Structural results — populated from full ablation runs in Phase 3.
const ROWS = [
  {
    config: "Full system (A + B + C)",
    effect: "Baseline — full recommendation quality",
    status: "active",
  },
  {
    config: "No ML prediction (A off)",
    effect: "Reacts only to injected disruptions; misses weather-driven cascades",
    status: "planned",
  },
  {
    config: "No simulation (B off)",
    effect: "Optimizer prices actions blind to downstream cascade effects",
    status: "planned",
  },
  {
    config: "Greedy instead of MILP (C↓)",
    effect: "Misses combined actions; see Method 3 cost gap",
    status: "measured",
  },
];

export default function AblationTable() {
  return (
    <div className="aero-card p-4">
      <div className="aero-label mb-2">Method 5 · component ablation</div>
      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-left text-aero-muted uppercase text-[9px] tracking-wider">
            <th className="py-1 pr-2">Configuration</th>
            <th className="py-1 pr-2">Effect</th>
            <th className="py-1">Status</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr key={r.config} className="border-t border-aero-border">
              <td className="py-1.5 pr-2 font-medium">{r.config}</td>
              <td className="py-1.5 pr-2 text-aero-muted">{r.effect}</td>
              <td className="py-1.5">
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] uppercase border ${
                    r.status === "active"
                      ? "text-aero-green border-green-500/30"
                      : r.status === "measured"
                        ? "text-aero-blue border-blue-500/30"
                        : "text-aero-muted border-aero-border"
                  }`}
                >
                  {r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
