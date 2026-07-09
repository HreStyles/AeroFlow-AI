// Method 2 — historical backtest / Monte Carlo stress results from
// GET /api/validation/backtest (computed offline after model training).
interface Props {
  data: Record<string, any> | null;
}

export default function BacktestResults({ data }: Props) {
  return (
    <div className="aero-card p-4">
      <div className="aero-label mb-2">Method 2 · backtest / Monte Carlo stress</div>
      {!data || data.available === false ? (
        <div className="text-xs text-aero-muted leading-relaxed">
          {data?.message ??
            "Backtest results not yet computed. Train the model, then run scripts/generate_presets.py."}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-3 text-center">
          <div>
            <div className="font-mono font-bold text-xl">{data.n_scenarios}</div>
            <div className="text-[10px] uppercase text-aero-muted">scenarios</div>
          </div>
          <div>
            <div className="font-mono font-bold text-xl text-aero-green">
              {data.avg_cost_reduction_vs_do_nothing_pct}%
            </div>
            <div className="text-[10px] uppercase text-aero-muted">
              avg cost reduction
            </div>
          </div>
          <div>
            <div className="font-mono font-bold text-xl">
              {data.avg_stability_pct}%
            </div>
            <div className="text-[10px] uppercase text-aero-muted">avg stability</div>
          </div>
        </div>
      )}
    </div>
  );
}
