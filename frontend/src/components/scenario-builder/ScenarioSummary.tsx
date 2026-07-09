// Review step before submit: per-flight summary + provenance counts
// ("N fields user-provided, M derived, K estimated").
import { useMemo } from "react";
import type { Flight } from "../../types/scenario";
import ProvenanceBadge from "../shared/ProvenanceBadge";

interface Props {
  flights: Flight[];
  airportCode: string;
}

const REQUIRED_PROVIDED = 15; // identification + schedule + aircraft + weather + congestion + gate
const OPTIONAL_FIELDS: (keyof Flight)[] = [
  "total_passengers",
  "connecting_passengers",
  "avg_connection_buffer_min",
  "crew_duty_start",
  "crew_hours_on_duty",
  "standby_crew_available",
  "seating_capacity",
];
const DERIVED_COUNT = 6; // runway, wake, body type, deplaning, boarding (+capacity when blank)

export default function ScenarioSummary({ flights, airportCode }: Props) {
  const counts = useMemo(() => {
    let provided = 0;
    let estimated = 0;
    for (const f of flights) {
      provided += REQUIRED_PROVIDED;
      for (const field of OPTIONAL_FIELDS) {
        if (f[field] === null || f[field] === undefined || f[field] === "") {
          estimated += 1;
        } else {
          provided += 1;
        }
      }
    }
    return { provided, estimated, derived: flights.length * DERIVED_COUNT };
  }, [flights]);

  return (
    <div className="aero-card p-4 space-y-3">
      <h3 className="font-semibold text-sm">Scenario summary — {airportCode}</h3>

      <div className="flex items-center gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <ProvenanceBadge provenance="user_provided" />
          <span className="font-mono">{counts.provided}</span> fields
        </span>
        <span className="flex items-center gap-1.5">
          <ProvenanceBadge provenance="derived" />
          <span className="font-mono">~{counts.derived}</span> fields
        </span>
        <span className="flex items-center gap-1.5">
          <ProvenanceBadge provenance="assumed_default" />
          <span className="font-mono">{counts.estimated}</span> fields
        </span>
      </div>

      <table className="w-full text-[11px]">
        <thead>
          <tr className="text-left text-aero-muted uppercase text-[9px] tracking-wider">
            <th className="py-1 pr-2">Flight</th>
            <th className="py-1 pr-2">Route</th>
            <th className="py-1 pr-2">Times</th>
            <th className="py-1 pr-2">Aircraft / tail</th>
            <th className="py-1 pr-2">Gate</th>
            <th className="py-1 pr-2">Weather O/D</th>
            <th className="py-1 pr-2">Disruption</th>
          </tr>
        </thead>
        <tbody>
          {flights.map((f, i) => (
            <tr key={i} className="border-t border-aero-border">
              <td className="py-1 pr-2 font-mono">{f.flight_id || "—"}</td>
              <td className="py-1 pr-2 font-mono">
                {f.origin}→{f.destination}
              </td>
              <td className="py-1 pr-2 font-mono">
                {f.scheduled_departure}–{f.scheduled_arrival}
              </td>
              <td className="py-1 pr-2 font-mono">
                {f.aircraft_type} / {f.tail_number || "—"}
              </td>
              <td className="py-1 pr-2 font-mono">{f.assigned_gate || "—"}</td>
              <td className="py-1 pr-2 font-mono">
                {f.origin_weather_severity.toFixed(2)}/
                {f.destination_weather_severity.toFixed(2)}
              </td>
              <td className="py-1 pr-2">
                {f.injected_delay_cause
                  ? `${f.injected_delay_cause} +${f.injected_delay_minutes}m`
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
