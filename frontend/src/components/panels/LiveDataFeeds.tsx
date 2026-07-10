// Bottom-left: weather, congestion, capacity, and aircraft status feeds
// derived from the scenario + current sim state.
import type { AirportConfig, Flight } from "../../types/scenario";
import type { TimedEvent } from "../../hooks/useSimulation";

interface Props {
  airport: AirportConfig;
  flights: Flight[];
  simTime: number;
  activeGdp: TimedEvent | null;
  flightStatus: Record<string, "normal" | "warning" | "disrupted">;
}

function severityLabel(s: number): { label: string; cls: string } {
  if (s >= 0.7) return { label: "SEVERE", cls: "text-aero-red" };
  if (s >= 0.4) return { label: "SIGNIFICANT", cls: "text-aero-amber" };
  if (s >= 0.2) return { label: "MARGINAL", cls: "text-aero-amber" };
  return { label: "CLEAR", cls: "text-aero-green" };
}

export default function LiveDataFeeds({
  airport,
  flights,
  activeGdp,
  flightStatus,
}: Props) {
  const real = flights.filter((f) => f.status !== "idle");
  const hubWx = Math.max(
    ...real.map((f) =>
      f.origin === airport.airport_code
        ? f.origin_weather_severity
        : f.destination_weather_severity
    ),
    0
  );
  const wx = severityLabel(hubWx);
  const imc = hubWx >= 0.5;
  const capacity = activeGdp
    ? activeGdp.details.reduced_acceptance_rate
    : imc
      ? airport.imc_capacity_per_hour
      : airport.vmc_capacity_per_hour;

  const congestion =
    real.find((f) => f.origin === airport.airport_code)?.origin_congestion ??
    real[0]?.destination_congestion ??
    "low";

  return (
    <div className="aero-card h-full flex flex-col overflow-hidden">
      <div className="panel-header">
        <span className="panel-title">Live data feeds</span>
        <span className="ml-auto flex items-center gap-1 text-[9px] font-mono text-aero-green">
          <span className="w-1.5 h-1.5 rounded-full bg-aero-green animate-pulse-alert" />
          LIVE
        </span>
      </div>
      <div className="p-3 flex flex-col gap-2 overflow-y-auto">

      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="bg-aero-bg rounded p-2">
          <div className="aero-label">Weather · {airport.airport_code}</div>
          <div className={`font-mono font-bold ${wx.cls}`}>{wx.label}</div>
          <div className="text-aero-muted">
            severity {hubWx.toFixed(2)} · {imc ? "IMC" : "VMC"}
          </div>
        </div>
        <div className="bg-aero-bg rounded p-2">
          <div className="aero-label">Capacity</div>
          <div className={`font-mono font-bold ${activeGdp ? "text-aero-red" : ""}`}>
            {capacity}/hr
          </div>
          <div className="text-aero-muted">
            {activeGdp
              ? `GDP active ${activeGdp.details.start_time}–${activeGdp.details.end_time}`
              : `${imc ? "IMC" : "VMC"} arrival rate`}
          </div>
        </div>
        <div className="bg-aero-bg rounded p-2">
          <div className="aero-label">Congestion</div>
          <div className="font-mono font-bold uppercase">{congestion}</div>
          <div className="text-aero-muted">surface + terminal area</div>
        </div>
        <div className="bg-aero-bg rounded p-2">
          <div className="aero-label">Passengers</div>
          <div className="font-mono font-bold">
            {real
              .reduce((sum, f) => sum + (f.total_passengers ?? 0), 0)
              .toLocaleString()}
          </div>
          <div className="text-aero-muted">
            {real.reduce((s, f) => s + (f.connecting_passengers ?? 0), 0)} connecting
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        <div className="aero-label mb-1">Aircraft status</div>
        <div className="space-y-0.5">
          {flights.map((f) => {
            const status = f.status === "idle" ? "spare" : flightStatus[f.flight_id] ?? "normal";
            const dot =
              status === "disrupted"
                ? "bg-aero-red"
                : status === "warning"
                  ? "bg-aero-amber"
                  : status === "spare"
                    ? "bg-slate-500"
                    : "bg-aero-green";
            return (
              <div key={f.flight_id} className="flex items-center gap-2 text-[11px]">
                <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
                <span className="font-mono w-16">{f.flight_id}</span>
                <span className="text-aero-muted font-mono w-16">{f.tail_number}</span>
                <span className="text-aero-muted">
                  {f.status === "idle"
                    ? `spare · ${f.aircraft_type}`
                    : `${f.origin}→${f.destination} · ${f.scheduled_departure}`}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      </div>
    </div>
  );
}
