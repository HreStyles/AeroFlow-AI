// Simulation playback state machine.
//
// All state derives from the precomputed event log + simTime — the backend
// is never called during playback. The loop advances simTime on a fixed
// interval; at 1x, one real second is one simulated minute (so a full
// airport day plays in minutes, and 50x steps through it in seconds).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EventLog, SimEvent } from "../types/events";
import { timeToSeconds } from "../utils/formatting";

export const SPEEDS = [1, 5, 10, 50] as const;
const TICK_MS = 50;
const SIM_SECONDS_PER_REAL_SECOND_AT_1X = 60;
const LEAD_IN_SECONDS = 120;

export interface TimedEvent extends SimEvent {
  index: number;
  t: number; // seconds since midnight
}

export interface SimulationState {
  simTime: number;
  speed: number;
  isPlaying: boolean;
  startTime: number;
  endTime: number;
  events: TimedEvent[];
  firedEvents: TimedEvent[];
  currentEventIndex: number; // index of most recent fired event, -1 if none
  activePrediction: TimedEvent | null;
  activeCascade: TimedEvent | null;
  activeRecommendation: TimedEvent | null;
  activeGdp: TimedEvent | null;
  flightDelays: Record<string, number>; // flight_id → delay seconds (P50 / injected)
  flightStatus: Record<string, "normal" | "warning" | "disrupted">;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  setSpeed: (s: number) => void;
  stepForward: () => void;
  jumpToEvent: (index: number) => void;
  reset: () => void;
}

export function useSimulation(eventLog: EventLog | null): SimulationState {
  const events = useMemo<TimedEvent[]>(
    () =>
      (eventLog?.events ?? []).map((e, index) => ({
        ...e,
        index,
        t: timeToSeconds(e.sim_time),
      })),
    [eventLog]
  );

  const startTime = useMemo(
    () => (events.length ? events[0].t - LEAD_IN_SECONDS : 0),
    [events]
  );
  const endTime = useMemo(
    () => (events.length ? events[events.length - 1].t + 15 * 60 : 0),
    [events]
  );

  const [simTime, setSimTime] = useState(startTime);
  const [speed, setSpeedState] = useState<number>(SPEEDS[1]);
  const [isPlaying, setIsPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Re-arm when a new event log loads
  useEffect(() => {
    setSimTime(startTime);
    setIsPlaying(false);
  }, [startTime, eventLog]);

  useEffect(() => {
    if (!isPlaying) return;
    // Advance by measured wall-clock delta (not a fixed per-tick amount) so
    // playback speed stays correct even when the browser throttles timers.
    let last = performance.now();
    intervalRef.current = setInterval(() => {
      const now = performance.now();
      const dt = (now - last) / 1000;
      last = now;
      setSimTime((t) => {
        const next = t + speed * SIM_SECONDS_PER_REAL_SECOND_AT_1X * dt;
        if (next >= endTime) {
          setIsPlaying(false);
          return endTime;
        }
        return next;
      });
    }, TICK_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isPlaying, speed, endTime]);

  const currentEventIndex = useMemo(() => {
    let idx = -1;
    for (const e of events) {
      if (e.t <= simTime) idx = e.index;
      else break;
    }
    return idx;
  }, [events, simTime]);

  const firedEvents = useMemo(
    () => events.slice(0, currentEventIndex + 1),
    [events, currentEventIndex]
  );

  const lastOfType = useCallback(
    (type: string): TimedEvent | null => {
      for (let i = firedEvents.length - 1; i >= 0; i--) {
        if (firedEvents[i].event_type === type) return firedEvents[i];
      }
      return null;
    },
    [firedEvents]
  );

  const activePrediction = useMemo(
    () => lastOfType("delay_predicted"),
    [lastOfType]
  );
  const activeCascade = useMemo(
    () => lastOfType("cascade_detected"),
    [lastOfType]
  );
  const activeRecommendation = useMemo(
    () => lastOfType("recommendation_generated"),
    [lastOfType]
  );
  const activeGdp = useMemo(() => {
    const started = lastOfType("gdp_started");
    const ended = lastOfType("gdp_ended");
    if (started && (!ended || ended.t < started.t)) return started;
    return null;
  }, [lastOfType]);

  // Per-flight delay (seconds) and visual status, from fired events
  const { flightDelays, flightStatus } = useMemo(() => {
    const delays: Record<string, number> = {};
    const status: Record<string, "normal" | "warning" | "disrupted"> = {};
    for (const e of firedEvents) {
      if (e.event_type === "delay_predicted" && e.flight_id) {
        delays[e.flight_id] = Math.max(
          delays[e.flight_id] ?? 0,
          (e.details.p50_minutes ?? 0) * 60
        );
        if (status[e.flight_id] !== "disrupted")
          status[e.flight_id] = "warning";
      } else if (e.event_type === "disruption_injected" && e.flight_id) {
        delays[e.flight_id] = Math.max(
          delays[e.flight_id] ?? 0,
          (e.details.delay_minutes ?? 0) * 60
        );
        status[e.flight_id] = "disrupted";
      } else if (e.event_type === "cascade_detected") {
        for (const af of e.details.affected_flights ?? []) {
          delays[af.flight_id] = Math.max(
            delays[af.flight_id] ?? 0,
            af.propagated_delay_minutes * 60
          );
          status[af.flight_id] = "disrupted";
        }
        if (e.flight_id) status[e.flight_id] = "disrupted";
      }
    }
    return { flightDelays: delays, flightStatus: status };
  }, [firedEvents]);

  const play = useCallback(() => {
    setSimTime((t) => (t >= endTime ? startTime : t));
    setIsPlaying(true);
  }, [endTime, startTime]);
  const pause = useCallback(() => setIsPlaying(false), []);
  const togglePlay = useCallback(
    () => (isPlaying ? pause() : play()),
    [isPlaying, pause, play]
  );
  const setSpeed = useCallback((s: number) => setSpeedState(s), []);

  const stepForward = useCallback(() => {
    setIsPlaying(false);
    const next = events.find((e) => e.t > simTime);
    if (next) setSimTime(next.t);
    else setSimTime(endTime);
  }, [events, simTime, endTime]);

  const jumpToEvent = useCallback(
    (index: number) => {
      const e = events[index];
      if (!e) return;
      setIsPlaying(false);
      setSimTime(e.t + 1);
    },
    [events]
  );

  const reset = useCallback(() => {
    setIsPlaying(false);
    setSimTime(startTime);
  }, [startTime]);

  return {
    simTime,
    speed,
    isPlaying,
    startTime,
    endTime,
    events,
    firedEvents,
    currentEventIndex,
    activePrediction,
    activeCascade,
    activeRecommendation,
    activeGdp,
    flightDelays,
    flightStatus,
    play,
    pause,
    togglePlay,
    setSpeed,
    stepForward,
    jumpToEvent,
    reset,
  };
}
