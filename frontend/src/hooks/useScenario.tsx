// Scenario loading/submission + shared state for the loaded event log.
// PresetsPage / ScenarioBuilderPage load a scenario here, then navigate to
// the SimulationPage which consumes it — the event log is fully loaded
// before playback starts (no backend calls during playback).
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError } from "../api/client";
import type { AirportConfig, Scenario } from "../types/scenario";
import type { EventLog } from "../types/events";

interface ScenarioState {
  eventLog: EventLog | null;
  airport: AirportConfig | null;
  loading: boolean;
  error: string | null;
  errorStatus: number | null;
  loadPreset: (id: string) => Promise<EventLog | null>;
  submitScenario: (scenario: Scenario) => Promise<EventLog | null>;
  clearError: () => void;
}

const ScenarioContext = createContext<ScenarioState | null>(null);

export function ScenarioProvider({ children }: { children: ReactNode }) {
  const [eventLog, setEventLog] = useState<EventLog | null>(null);
  const [airport, setAirport] = useState<AirportConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);

  const ingest = useCallback(async (log: EventLog) => {
    const airportConfig = await api.getAirport(log.airport_code);
    setEventLog(log);
    setAirport(airportConfig);
    return log;
  }, []);

  const wrap = useCallback(
    async (fn: () => Promise<EventLog>): Promise<EventLog | null> => {
      setLoading(true);
      setError(null);
      setErrorStatus(null);
      try {
        return await ingest(await fn());
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
        setErrorStatus(e instanceof ApiError ? e.status : null);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [ingest]
  );

  const loadPreset = useCallback(
    (id: string) => wrap(() => api.getPreset(id)),
    [wrap]
  );

  const submitScenario = useCallback(
    (scenario: Scenario) => wrap(() => api.simulate(scenario)),
    [wrap]
  );

  const clearError = useCallback(() => {
    setError(null);
    setErrorStatus(null);
  }, []);

  return (
    <ScenarioContext.Provider
      value={{
        eventLog,
        airport,
        loading,
        error,
        errorStatus,
        loadPreset,
        submitScenario,
        clearError,
      }}
    >
      {children}
    </ScenarioContext.Provider>
  );
}

export function useScenario(): ScenarioState {
  const ctx = useContext(ScenarioContext);
  if (!ctx) throw new Error("useScenario must be used inside ScenarioProvider");
  return ctx;
}
