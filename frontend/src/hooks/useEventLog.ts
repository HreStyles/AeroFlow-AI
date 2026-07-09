// Event log navigation helpers: timeline markers with % positions for the
// EventTimeline strip, and jump-to-event support.
import { useMemo } from "react";
import type { TimedEvent } from "./useSimulation";

const MARKER_TYPES = new Set([
  "disruption_injected",
  "delay_predicted",
  "cascade_detected",
  "recommendation_generated",
  "gdp_started",
  "gdp_ended",
]);

export interface TimelineMarker {
  event: TimedEvent;
  positionPct: number;
  fired: boolean;
}

export function useEventLog(
  events: TimedEvent[],
  startTime: number,
  endTime: number,
  simTime: number
) {
  const markers = useMemo<TimelineMarker[]>(() => {
    const span = Math.max(1, endTime - startTime);
    return events
      .filter((e) => MARKER_TYPES.has(e.event_type))
      .map((e) => ({
        event: e,
        positionPct: ((e.t - startTime) / span) * 100,
        fired: e.t <= simTime,
      }));
  }, [events, startTime, endTime, simTime]);

  const progressPct = useMemo(() => {
    const span = Math.max(1, endTime - startTime);
    return Math.min(100, Math.max(0, ((simTime - startTime) / span) * 100));
  }, [simTime, startTime, endTime]);

  return { markers, progressPct };
}
