// SVG airport schematic — the dashboard's hero. Static layout (runways with
// centerlines/thresholds, taxiways, concourse piers, gate stubs) plus a
// dynamic narration layer that shows exactly what the pipeline is doing:
//   • aircraft animated from the event log, colored by status
//   • delay-prediction callout pinned to the trigger aircraft (Component A)
//   • cascade arrows from the trigger to affected downstream flights (B)
//   • dashed gate-reassignment path + aircraft-swap link (Component C)
import { useMemo } from "react";
import type { AirportConfig, Flight } from "../../types/scenario";
import type { TimedEvent } from "../../hooks/useSimulation";
import { aircraftPosition, gatePosition } from "../../utils/interpolation";
import AircraftIcon from "./AircraftIcon";
import GateStatus from "./GateStatus";
import RunwayStatus from "./RunwayStatus";

interface Props {
  airport: AirportConfig;
  flights: Flight[];
  simTime: number;
  flightDelays: Record<string, number>;
  flightStatus: Record<string, "normal" | "warning" | "disrupted">;
  activePrediction: TimedEvent | null;
  activeRecommendation: TimedEvent | null;
  activeCascade: TimedEvent | null;
  gdpActive: boolean;
}

export default function AirportMap({
  airport,
  flights,
  simTime,
  flightDelays,
  flightStatus,
  activePrediction,
  activeRecommendation,
  activeCascade,
  gdpActive,
}: Props) {
  const layout = airport.map_layout;

  const positioned = useMemo(() => {
    if (!layout) return [];
    return flights
      .map((f) => ({
        flight: f,
        pos: aircraftPosition(
          f, layout, airport.airport_code, simTime,
          flightDelays[f.flight_id] ?? 0
        ),
      }))
      .filter((p) => p.pos && p.pos.visible);
  }, [flights, layout, airport.airport_code, simTime, flightDelays]);

  const posById = useMemo(() => {
    const m: Record<string, { x: number; y: number }> = {};
    for (const p of positioned) m[p.flight.flight_id] = { x: p.pos!.x, y: p.pos!.y };
    return m;
  }, [positioned]);

  const occupiedGates = useMemo(() => {
    const set = new Set<string>();
    for (const p of positioned) {
      if (p.pos!.phase === "parked") set.add(p.flight.assigned_gate);
    }
    return set;
  }, [positioned]);

  const conflictGates = useMemo(() => {
    const set = new Set<string>();
    for (const gc of activeCascade?.details.gate_conflicts ?? []) set.add(gc.gate);
    return set;
  }, [activeCascade]);

  // ── Component C overlays: gate reassignment path + aircraft swap link ─────
  const recActions = useMemo(() => {
    if (!layout || !activeRecommendation) return { gate: null, swap: null } as any;
    const top = activeRecommendation.details.ranked_options?.[0];
    if (!top) return { gate: null, swap: null };
    const leaves = top.action_details?.components ?? [top.action_details];
    const gateAction = leaves.find((a: any) => a?.type === "gate_reassignment");
    const swapAction = leaves.find((a: any) => a?.type === "aircraft_swap");
    let gate = null;
    if (gateAction) {
      const from = gatePosition(layout, gateAction.from_gate);
      const to = gatePosition(layout, gateAction.to_gate);
      if (from && to) gate = { from, to, toGate: gateAction.to_gate };
    }
    let swap = null;
    if (swapAction) {
      const spare = flights.find((f) => f.tail_number === swapAction.to_tail);
      const target = flights.find((f) => f.flight_id === swapAction.flight_id);
      if (spare && target) {
        const a = posById[spare.flight_id] ?? gatePosition(layout, spare.assigned_gate);
        const b = posById[target.flight_id] ?? gatePosition(layout, target.assigned_gate);
        if (a && b) swap = { a, b, tail: swapAction.to_tail };
      }
    }
    return { gate, swap };
  }, [layout, activeRecommendation, flights, posById]);

  // ── Component B overlay: cascade arrows trigger → affected flights ────────
  const cascadeArrows = useMemo(() => {
    if (!layout || !activeCascade) return [];
    const trigger = activeCascade.details.trigger_flight as string;
    const from =
      posById[trigger] ??
      gatePosition(layout, flights.find((f) => f.flight_id === trigger)?.assigned_gate ?? "");
    if (!from) return [];
    const arrows = [];
    for (const af of activeCascade.details.affected_flights ?? []) {
      const target = flights.find((f) => f.flight_id === af.flight_id);
      if (!target) continue;
      const to = posById[af.flight_id] ?? gatePosition(layout, target.assigned_gate);
      if (!to || (to.x === from.x && to.y === from.y)) continue;
      arrows.push({ from, to, label: `+${Math.round(af.propagated_delay_minutes)}m`, id: af.flight_id });
    }
    return arrows;
  }, [layout, activeCascade, flights, posById]);

  // ── Component A overlay: prediction callout above the trigger aircraft ────
  const callout = useMemo(() => {
    if (!layout || !activePrediction) return null;
    const fid = activePrediction.details.flight_id as string;
    const anchor =
      posById[fid] ??
      gatePosition(layout, flights.find((f) => f.flight_id === fid)?.assigned_gate ?? "");
    if (!anchor) return null;
    const p = activePrediction.details;
    const x = Math.min(Math.max(anchor.x, 110), layout.width - 110);
    const y = Math.max(anchor.y - 44, 46);
    return {
      x, y, anchorX: anchor.x, anchorY: anchor.y - 26,
      line1: `${fid} · P(delay) ${Math.round(p.probability * 100)}%`,
      line2: `P50 ${p.p50_minutes}m · P90 ${p.p90_minutes}m`,
      severe: p.probability >= 0.6,
    };
  }, [layout, activePrediction, flights, posById]);

  const imc = useMemo(
    () =>
      flights.some(
        (f) =>
          (f.origin === airport.airport_code
            ? f.origin_weather_severity
            : f.destination_weather_severity) >= 0.5
      ),
    [flights, airport.airport_code]
  );

  if (!layout) {
    return (
      <div className="h-full flex items-center justify-center text-aero-muted text-sm">
        No map layout available for {airport.airport_code}
      </div>
    );
  }

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="w-full h-full"
      preserveAspectRatio="xMidYMid meet"
    >
      <defs>
        <pattern id="map-grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#13203a" strokeWidth="0.6" />
        </pattern>
        <radialGradient id="map-glow" cx="50%" cy="45%" r="75%">
          <stop offset="0%" stopColor="#0f1a2e" />
          <stop offset="100%" stopColor="#0a0f1a" />
        </radialGradient>
        <linearGradient id="pier" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#22314c" />
          <stop offset="100%" stopColor="#182338" />
        </linearGradient>
        <marker id="arrow-red" viewBox="0 0 8 8" refX="7" refY="4"
          markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0.5 L7.5,4 L0,7.5 Z" fill="#ef4444" />
        </marker>
      </defs>

      {/* base */}
      <rect width={layout.width} height={layout.height} fill="url(#map-glow)" rx="8" />
      <rect width={layout.width} height={layout.height} fill="url(#map-grid)" rx="8" />

      {/* header block */}
      <text x={18} y={30} fontSize={15} fontWeight={700} fill="#3f5573" className="font-mono">
        {airport.airport_code}
      </text>
      <text x={62} y={30} fontSize={10} fill="#31425c" className="font-mono">
        {airport.airport_name?.toUpperCase()}
      </text>
      {/* condition chip */}
      <g transform={`translate(${layout.width - 18}, 20)`}>
        <text textAnchor="end" fontSize={10} fontWeight={600} className="font-mono"
          fill={gdpActive ? "#ef4444" : imc ? "#f59e0b" : "#22c55e"}>
          {gdpActive ? "◼ GDP ACTIVE — ARRIVALS METERED" : imc ? "◆ IMC OPERATIONS" : "● VMC OPERATIONS"}
        </text>
        <text textAnchor="end" y={14} fontSize={9} fill="#3f5573" className="font-mono">
          {(imc ? airport.imc_capacity_per_hour : airport.vmc_capacity_per_hour)}/HR ACCEPTANCE
        </text>
      </g>

      {/* taxiways */}
      {layout.taxiways?.map((tw) => (
        <g key={tw.id}>
          <polyline
            points={tw.points.map((p) => p.join(",")).join(" ")}
            fill="none" stroke="#16223a" strokeWidth={9}
            strokeLinecap="round" strokeLinejoin="round"
          />
          <polyline
            points={tw.points.map((p) => p.join(",")).join(" ")}
            fill="none" stroke="#f0c94a" strokeWidth={0.8} opacity={0.25}
            strokeLinecap="round" strokeLinejoin="round"
          />
        </g>
      ))}

      {layout.runways.map((rw) => (
        <RunwayStatus key={rw.id} runway={rw} gdpActive={gdpActive} />
      ))}

      {/* concourse piers + gates */}
      {layout.concourses.map((c) => {
        const width = 58 + (c.gate_positions?.length ?? c.gates.length) * 44;
        return (
          <g key={c.id}>
            <rect x={c.x} y={c.y - 2} width={width} height={22} rx={10}
              fill="url(#pier)" stroke="#2b3a52" strokeWidth={1} />
            <circle cx={c.x + 15} cy={c.y + 9} r={8.5} fill="#0a0f1a" stroke="#3b82f6"
              strokeWidth={1} opacity={0.9} />
            <text x={c.x + 15} y={c.y + 12.5} textAnchor="middle" fontSize={10}
              fontWeight={700} fill="#7ba4e8" className="font-mono">
              {c.id.replace("T", "").slice(0, 2) || c.id}
            </text>
            {(c.gate_positions ?? []).map((g) => (
              <g key={g.id} transform={`translate(0, 14)`}>
                <GateStatus
                  x={g.x} y={g.y}
                  gate={g.id}
                  occupied={occupiedGates.has(g.id)}
                  conflict={conflictGates.has(g.id)}
                  highlight={recActions.gate?.toGate === g.id}
                />
              </g>
            ))}
          </g>
        );
      })}

      {/* ── Component B: cascade propagation arrows ── */}
      {cascadeArrows.map((a) => {
        const mx = (a.from.x + a.to.x) / 2;
        const my = Math.min(a.from.y, a.to.y) - 36;
        return (
          <g key={a.id}>
            <path
              d={`M ${a.from.x} ${a.from.y} Q ${mx} ${my} ${a.to.x} ${a.to.y - 8}`}
              fill="none" stroke="#ef4444" strokeWidth={1.6}
              strokeDasharray="6 5" markerEnd="url(#arrow-red)"
              className="animate-dash-flow" opacity={0.85}
            />
            <text x={mx} y={my + 12} textAnchor="middle" fontSize={9.5} fontWeight={700}
              fill="#f87171" className="font-mono">
              {a.label}
            </text>
          </g>
        );
      })}

      {/* ── Component C: gate reassignment path ── */}
      {recActions.gate && (
        <g>
          <line
            x1={recActions.gate.from.x} y1={recActions.gate.from.y + 8}
            x2={recActions.gate.to.x} y2={recActions.gate.to.y + 8}
            stroke="#3b82f6" strokeWidth={2} strokeDasharray="8 6"
            className="animate-dash-flow"
          />
          <circle cx={recActions.gate.to.x} cy={recActions.gate.to.y + 8} r={8}
            fill="none" stroke="#3b82f6" strokeWidth={2} />
          <text x={recActions.gate.to.x} y={recActions.gate.to.y + 34} textAnchor="middle"
            fontSize={9} fontWeight={700} fill="#93c5fd" className="font-mono">
            → {recActions.gate.toGate}
          </text>
        </g>
      )}

      {/* ── Component C: aircraft swap link ── */}
      {recActions.swap && (
        <g>
          <line
            x1={recActions.swap.a.x} y1={recActions.swap.a.y}
            x2={recActions.swap.b.x} y2={recActions.swap.b.y}
            stroke="#22c55e" strokeWidth={1.6} strokeDasharray="4 4"
            className="animate-dash-flow" opacity={0.8}
          />
          <g transform={`translate(${(recActions.swap.a.x + recActions.swap.b.x) / 2}, ${(recActions.swap.a.y + recActions.swap.b.y) / 2})`}>
            <rect x={-30} y={-9} width={60} height={16} rx={8} fill="#0a0f1a"
              stroke="#22c55e" strokeWidth={1} opacity={0.95} />
            <text textAnchor="middle" y={3.5} fontSize={9} fontWeight={700}
              fill="#4ade80" className="font-mono">
              ⇄ SWAP
            </text>
          </g>
        </g>
      )}

      {/* aircraft */}
      {positioned.map(({ flight, pos }) => (
        <AircraftIcon
          key={flight.flight_id}
          x={pos!.x} y={pos!.y}
          rotation={pos!.rotation}
          status={flightStatus[flight.flight_id] ?? "normal"}
          label={flight.flight_id}
          isSpare={flight.status === "idle"}
          opacity={pos!.opacity}
          moving={pos!.phase === "taxi_in" || pos!.phase === "taxi_out" || pos!.phase === "approach"}
          highlighted={
            activeRecommendation?.details.trigger_flight === flight.flight_id ||
            activeCascade?.details.trigger_flight === flight.flight_id
          }
        />
      ))}

      {/* ── Component A: prediction callout ── */}
      {callout && (
        <g className="animate-fade-up">
          <line x1={callout.anchorX} y1={callout.anchorY} x2={callout.x} y2={callout.y + 16}
            stroke={callout.severe ? "#ef4444" : "#f59e0b"} strokeWidth={1} opacity={0.6} />
          <rect x={callout.x - 92} y={callout.y - 18} width={184} height={34} rx={6}
            fill="#0d1526" stroke={callout.severe ? "#ef4444" : "#f59e0b"}
            strokeWidth={1.2} opacity={0.97} />
          <text x={callout.x} y={callout.y - 5} textAnchor="middle" fontSize={10}
            fontWeight={700} fill={callout.severe ? "#f87171" : "#fbbf24"} className="font-mono">
            ⚠ {callout.line1}
          </text>
          <text x={callout.x} y={callout.y + 9} textAnchor="middle" fontSize={9}
            fill="#8ba3c7" className="font-mono">
            {callout.line2}
          </text>
        </g>
      )}

      {/* legend */}
      <g transform={`translate(18, ${layout.height - 16})`} fontSize={9} className="font-mono">
        {[
          { c: "#22c55e", t: "ON TIME" },
          { c: "#f59e0b", t: "DELAY PREDICTED" },
          { c: "#ef4444", t: "DISRUPTED" },
          { c: "#64748b", t: "SPARE" },
        ].map((item, i) => (
          <g key={item.t} transform={`translate(${i * 118}, 0)`}>
            <circle r={3.5} fill={item.c} cy={-3} />
            <text x={8} fill="#4a5f7d">{item.t}</text>
          </g>
        ))}
        <g transform="translate(472, 0)">
          <line x1={-2} y1={-3} x2={14} y2={-3} stroke="#ef4444" strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={19} fill="#4a5f7d">CASCADE</text>
        </g>
        <g transform="translate(576, 0)">
          <line x1={-2} y1={-3} x2={14} y2={-3} stroke="#3b82f6" strokeWidth={1.5} strokeDasharray="4 3" />
          <text x={19} fill="#4a5f7d">REASSIGNMENT</text>
        </g>
      </g>
    </svg>
  );
}
