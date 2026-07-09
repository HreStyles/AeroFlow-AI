// Aircraft position interpolation for map animation.
//
// All positions derive from the precomputed event log + static airport
// layout — no physics, just linear interpolation between key points:
//   departures:  parked at gate → taxi to runway → takeoff roll + climb-out
//                (fading) → gone
//   arrivals:    approach along the runway heading (fading in) → touchdown →
//                taxi to gate → parked
import type { Flight, MapLayout } from "../types/scenario";
import { timeToSeconds } from "./formatting";

export const TAXI_SECONDS = 8 * 60;
export const APPROACH_SECONDS = 6 * 60;
export const CLIMBOUT_SECONDS = 3 * 60;

export interface AircraftPosition {
  x: number;
  y: number;
  visible: boolean;
  phase: "parked" | "taxi_out" | "climb_out" | "approach" | "airborne" | "taxi_in" | "done";
  rotation: number; // degrees, for the aircraft icon heading
  opacity: number;
}

export function gatePosition(
  layout: MapLayout,
  gate: string
): { x: number; y: number } | null {
  for (const concourse of layout.concourses) {
    const pos = concourse.gate_positions?.find((g) => g.id === gate);
    if (pos) return { x: pos.x, y: pos.y };
    const idx = concourse.gates.indexOf(gate);
    if (idx >= 0) return { x: concourse.x + 40 + idx * 44, y: concourse.y + 26 };
  }
  return null;
}

interface Point {
  x: number;
  y: number;
}

function runwayGeometry(layout: MapLayout, index = 0) {
  const rw = layout.runways[index % layout.runways.length];
  if (!rw) {
    return {
      mid: { x: 100, y: 100 },
      threshold: { x: 60, y: 100 },
      heading: { x: 1, y: 0 },
    };
  }
  const mid = { x: (rw.x1 + rw.x2) / 2, y: (rw.y1 + rw.y2) / 2 };
  const len = Math.hypot(rw.x2 - rw.x1, rw.y2 - rw.y1) || 1;
  const heading = { x: (rw.x2 - rw.x1) / len, y: (rw.y2 - rw.y1) / len };
  return { mid, threshold: { x: rw.x1, y: rw.y1 }, heading, length: len };
}

function lerp(a: Point, b: Point, t: number): Point {
  const k = Math.max(0, Math.min(1, t));
  return { x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k };
}

function heading(a: Point, b: Point): number {
  return (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI;
}

/**
 * Position of one aircraft at simTime (seconds since midnight).
 * airportCode determines whether this flight departs from or arrives at the
 * mapped airport; delaySeconds shifts the departure/arrival anchors.
 */
export function aircraftPosition(
  flight: Flight,
  layout: MapLayout,
  airportCode: string,
  simTime: number,
  delaySeconds = 0
): AircraftPosition | null {
  const gate = gatePosition(layout, flight.assigned_gate);
  if (!gate) return null;

  const isSpare = flight.status === "idle";
  if (isSpare) {
    return { ...gate, visible: true, phase: "parked", rotation: 0, opacity: 1 };
  }

  const departs = flight.origin === airportCode;
  const arrives = flight.destination === airportCode;
  const dep = timeToSeconds(flight.scheduled_departure) + delaySeconds;
  const arr = timeToSeconds(flight.scheduled_arrival) + delaySeconds;
  const rw = runwayGeometry(layout, flight.flight_number % 2);

  if (departs) {
    if (simTime < dep) {
      return { ...gate, visible: true, phase: "parked", rotation: 0, opacity: 1 };
    }
    if (simTime < dep + TAXI_SECONDS) {
      const t = (simTime - dep) / TAXI_SECONDS;
      const pos = lerp(gate, rw.mid, t);
      return {
        ...pos,
        visible: true,
        phase: "taxi_out",
        rotation: heading(gate, rw.mid),
        opacity: 1,
      };
    }
    if (simTime < dep + TAXI_SECONDS + CLIMBOUT_SECONDS) {
      // Takeoff roll + climb-out: accelerate along the runway heading past
      // the far end, fading as the aircraft "lifts off" the map.
      const t = (simTime - dep - TAXI_SECONDS) / CLIMBOUT_SECONDS;
      const reach = (rw.length ?? 300) * 0.9;
      const pos = {
        x: rw.mid.x + rw.heading.x * reach * t * t,
        y: rw.mid.y + rw.heading.y * reach * t * t,
      };
      return {
        ...pos,
        visible: true,
        phase: "climb_out",
        rotation: heading(rw.mid, { x: rw.mid.x + rw.heading.x, y: rw.mid.y + rw.heading.y }),
        opacity: Math.max(0, 1 - t),
      };
    }
    if (arrives && simTime >= arr) {
      // Turnaround flight returning to the same airport (rare) — parked.
      return { ...gate, visible: true, phase: "parked", rotation: 0, opacity: 1 };
    }
    return { ...rw.mid, visible: false, phase: "airborne", rotation: 0, opacity: 0 };
  }

  if (arrives) {
    if (simTime < arr - APPROACH_SECONDS) {
      return { ...rw.mid, visible: false, phase: "airborne", rotation: 0, opacity: 0 };
    }
    if (simTime < arr) {
      // Final approach: fly in along the runway heading toward the threshold,
      // fading in from "off the map".
      const t = (simTime - (arr - APPROACH_SECONDS)) / APPROACH_SECONDS;
      const reach = (rw.length ?? 300) * 1.2;
      const start = {
        x: rw.threshold.x - rw.heading.x * reach,
        y: rw.threshold.y - rw.heading.y * reach,
      };
      const pos = lerp(start, rw.mid, t);
      return {
        ...pos,
        visible: true,
        phase: "approach",
        rotation: heading(start, rw.mid),
        opacity: Math.min(1, 0.3 + t),
      };
    }
    if (simTime < arr + TAXI_SECONDS) {
      const t = (simTime - arr) / TAXI_SECONDS;
      const pos = lerp(rw.mid, gate, t);
      return {
        ...pos,
        visible: true,
        phase: "taxi_in",
        rotation: heading(rw.mid, gate),
        opacity: 1,
      };
    }
    return { ...gate, visible: true, phase: "parked", rotation: 0, opacity: 1 };
  }

  return null; // flight doesn't touch the mapped airport
}
