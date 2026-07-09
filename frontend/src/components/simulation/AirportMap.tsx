// SVG airport map: static layout (runways, concourses, gates) + animated
// aircraft at positions interpolated from the event log, plus a dashed
// reassignment path when a recommendation is active.
import { useMemo } from "react";
import type { AirportConfig, Flight } from "../../types/scenario";
import type { TimedEvent } from "../../hooks/useSimulation";
import {
  aircraftPosition,
  gatePosition,
} from "../../utils/interpolation";
import AircraftIcon from "./AircraftIcon";
import GateStatus from "./GateStatus";
import RunwayStatus from "./RunwayStatus";

interface Props {
  airport: AirportConfig;
  flights: Flight[];
  simTime: number;
  flightDelays: Record<string, number>;
  flightStatus: Record<string, "normal" | "warning" | "disrupted">;
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
          f,
          layout,
          airport.airport_code,
          simTime,
          flightDelays[f.flight_id] ?? 0
        ),
      }))
      .filter((p) => p.pos && p.pos.visible);
  }, [flights, layout, airport.airport_code, simTime, flightDelays]);

  const occupiedGates = useMemo(() => {
    const set = new Set<string>();
    for (const p of positioned) {
      if (p.pos!.phase === "parked") set.add(p.flight.assigned_gate);
    }
    return set;
  }, [positioned]);

  const conflictGates = useMemo(() => {
    const set = new Set<string>();
    for (const gc of activeCascade?.details.gate_conflicts ?? []) {
      set.add(gc.gate);
    }
    return set;
  }, [activeCascade]);

  // Dashed reassignment path for the rank-1 gate reassignment, if any
  const reassignmentPath = useMemo(() => {
    if (!layout || !activeRecommendation) return null;
    const top = activeRecommendation.details.ranked_options?.[0];
    if (!top) return null;
    const leaves = top.action_details?.components ?? [top.action_details];
    const gateAction = leaves.find(
      (a: Record<string, any>) => a?.type === "gate_reassignment"
    );
    if (!gateAction) return null;
    const from = gatePosition(layout, gateAction.from_gate);
    const to = gatePosition(layout, gateAction.to_gate);
    if (!from || !to) return null;
    return { from, to, toGate: gateAction.to_gate as string };
  }, [layout, activeRecommendation]);

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
      {/* ── static base layer ── */}
      <text x={16} y={28} fontSize={15} fill="#334155" className="font-mono font-bold">
        {airport.airport_code} · {airport.airport_name}
      </text>

      {layout.taxiways?.map((tw) => (
        <polyline
          key={tw.id}
          points={tw.points.map((p) => p.join(",")).join(" ")}
          fill="none"
          stroke="#16223a"
          strokeWidth={8}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}

      {layout.runways.map((rw) => (
        <RunwayStatus key={rw.id} runway={rw} gdpActive={gdpActive} />
      ))}

      {layout.concourses.map((c) => {
        const width = 60 + (c.gate_positions?.length ?? c.gates.length) * 44;
        return (
          <g key={c.id}>
            <rect
              x={c.x}
              y={c.y}
              width={width}
              height={20}
              rx={9}
              fill="#16223a"
              stroke="#1e293b"
            />
            <text
              x={c.x + 16}
              y={c.y + 14}
              fontSize={11}
              fill="#64748b"
              className="font-mono font-bold"
            >
              {c.id}
            </text>
            {(c.gate_positions ?? []).map((g) => (
              <GateStatus
                key={g.id}
                x={g.x}
                y={g.y}
                gate={g.id}
                occupied={occupiedGates.has(g.id)}
                conflict={conflictGates.has(g.id)}
                highlight={reassignmentPath?.toGate === g.id}
              />
            ))}
          </g>
        );
      })}

      {/* ── recommendation overlay: dashed gate-reassignment path ── */}
      {reassignmentPath && (
        <g>
          <line
            x1={reassignmentPath.from.x}
            y1={reassignmentPath.from.y}
            x2={reassignmentPath.to.x}
            y2={reassignmentPath.to.y}
            stroke="#ef4444"
            strokeWidth={2}
            strokeDasharray="7 5"
            className="animate-pulse-alert"
          />
          <circle
            cx={reassignmentPath.to.x}
            cy={reassignmentPath.to.y}
            r={7}
            fill="none"
            stroke="#ef4444"
            strokeWidth={2}
          />
        </g>
      )}

      {/* ── dynamic layer: aircraft ── */}
      {positioned.map(({ flight, pos }) => (
        <AircraftIcon
          key={flight.flight_id}
          x={pos!.x}
          y={pos!.y}
          rotation={pos!.rotation}
          status={flightStatus[flight.flight_id] ?? "normal"}
          label={flight.flight_id}
          isSpare={flight.status === "idle"}
          opacity={pos!.opacity}
          highlighted={
            activeRecommendation?.details.trigger_flight === flight.flight_id ||
            activeCascade?.details.trigger_flight === flight.flight_id
          }
        />
      ))}
    </svg>
  );
}
