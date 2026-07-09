// Validation dashboard: Methods 1–5. Methods 1/3/4 come from the most
// recently run scenario's ValidationResults; Method 2 from the backtest
// endpoint; Method 5 is the ablation table.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import AblationTable from "../components/validation/AblationTable";
import BacktestResults from "../components/validation/BacktestResults";
import BaselineComparison from "../components/validation/BaselineComparison";
import OptimalityGap from "../components/validation/OptimalityGap";
import SensitivityHeatmap from "../components/validation/SensitivityHeatmap";
import { api } from "../api/client";
import { useScenario } from "../hooks/useScenario";

export default function ValidationPage() {
  const { eventLog } = useScenario();
  const [backtest, setBacktest] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    api.getBacktest().then(setBacktest).catch(() => setBacktest(null));
  }, []);

  const validation = eventLog?.validation ?? null;

  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto p-6 space-y-4">
        <div>
          <h1 className="text-xl font-bold">Validation dashboard</h1>
          <p className="text-sm text-aero-muted">
            How do we know the recommendations are good? Five validation
            methods — no ground truth required for 1, 3, and 4.
          </p>
        </div>

        {!validation && (
          <div className="rounded border border-aero-border bg-aero-card text-sm px-4 py-3 text-aero-muted">
            Methods 1, 3, and 4 are computed per scenario.{" "}
            <Link to="/presets" className="text-aero-blue underline">
              Run a preset
            </Link>{" "}
            to populate them.
          </div>
        )}

        {validation && eventLog && (
          <div className="text-xs text-aero-muted">
            Showing results for{" "}
            <span className="font-mono text-aero-text">{eventLog.scenario_name}</span>
            {eventLog.prediction_source.startsWith("heuristic") && (
              <span className="text-aero-amber"> · heuristic predictions (model not trained)</span>
            )}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-4">
          <OptimalityGap gapPct={validation?.optimality_gap_pct ?? null} />
          <SensitivityHeatmap sensitivity={validation?.sensitivity ?? null} />
        </div>

        {validation && <BaselineComparison costs={validation.baseline_costs} />}

        <BacktestResults data={backtest} />
        <AblationTable />
      </div>
    </PageLayout>
  );
}
