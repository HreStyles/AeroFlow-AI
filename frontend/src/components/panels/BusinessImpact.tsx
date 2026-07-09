// Bottom bar: aggregate business metrics for the scenario so far.
import { useMemo } from "react";
import type { TimedEvent } from "../../hooks/useSimulation";
import type { ValidationResults } from "../../types/events";
import { formatCost } from "../../utils/formatting";

interface Props {
  firedEvents: TimedEvent[];
  totalFlights: number;
  validation: ValidationResults;
}

export default function BusinessImpact({ firedEvents, totalFlights, validation }: Props) {
  const stats = useMemo(() => {
    let delayedFlights = new Set<string>();
    let missedConnections = 0;
    let downstreamMinutes = 0;
    let doNothingCost = 0;
    let recommendedCost = 0;
    for (const e of firedEvents) {
      if (e.event_type === "delay_predicted" && e.flight_id) {
        delayedFlights.add(e.flight_id);
      }
      if (e.event_type === "cascade_detected") {
        missedConnections += e.details.missed_connections ?? 0;
        downstreamMinutes += e.details.total_downstream_delay_minutes ?? 0;
        doNothingCost += e.details.baseline_cost ?? 0;
      }
      if (e.event_type === "recommendation_generated") {
        recommendedCost += e.details.ranked_options?.[0]?.expected_cost ?? 0;
      }
    }
    return {
      delayed: delayedFlights.size,
      missedConnections,
      downstreamMinutes,
      doNothingCost,
      savings: Math.max(0, doNothingCost - recommendedCost),
    };
  }, [firedEvents]);

  const otp =
    totalFlights > 0
      ? Math.round(((totalFlights - stats.delayed) / totalFlights) * 100)
      : 100;

  const cells = [
    {
      label: "On-time performance",
      value: `${otp}%`,
      cls: otp >= 80 ? "text-aero-green" : otp >= 60 ? "text-aero-amber" : "text-aero-red",
    },
    {
      label: "Flights at risk",
      value: `${stats.delayed}/${totalFlights}`,
      cls: stats.delayed ? "text-aero-amber" : "text-aero-green",
    },
    {
      label: "Missed connections at risk",
      value: String(stats.missedConnections),
      cls: stats.missedConnections ? "text-aero-red" : "text-aero-green",
    },
    {
      label: "Downstream delay",
      value: `${Math.round(stats.downstreamMinutes)} min`,
      cls: stats.downstreamMinutes ? "text-aero-amber" : "text-aero-green",
    },
    {
      label: "Do-nothing exposure",
      value: formatCost(stats.doNothingCost),
      cls: "text-aero-red",
    },
    {
      label: "AI-recovered value",
      value: formatCost(stats.savings),
      cls: "text-aero-green",
    },
    {
      label: "MILP optimality gap",
      value: `${validation.optimality_gap_pct.toFixed(2)}%`,
      cls: "text-aero-blue",
    },
  ];

  return (
    <div className="aero-card px-4 py-2 flex items-center gap-6 overflow-x-auto">
      <span className="aero-label shrink-0">Business impact</span>
      {cells.map((c) => (
        <div key={c.label} className="shrink-0">
          <div className={`font-mono font-bold text-sm ${c.cls}`}>{c.value}</div>
          <div className="text-[9px] uppercase tracking-wider text-aero-muted">
            {c.label}
          </div>
        </div>
      ))}
    </div>
  );
}
