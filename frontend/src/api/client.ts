// Typed fetch wrapper for the AeroFlow backend API.
// Uses relative /api URLs — Vite proxies to the backend in dev.
import type { AirportConfig, PresetSummary, Scenario } from "../types/scenario";
import type { EventLog } from "../types/events";
import type { OperatorDecisionRecord } from "../types/recommendations";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export interface HealthStatus {
  status: string;
  model_trained: boolean;
  prediction_source: string;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),

  getPresets: () => request<{ presets: PresetSummary[] }>("/api/presets"),

  getPreset: (id: string) => request<EventLog>(`/api/presets/${id}`),

  simulate: (scenario: Scenario) =>
    request<EventLog>("/api/simulate", {
      method: "POST",
      body: JSON.stringify(scenario),
    }),

  postDecision: (scenarioId: string, decision: OperatorDecisionRecord) =>
    request<{ logged: boolean }>(`/api/simulate/${scenarioId}/decision`, {
      method: "POST",
      body: JSON.stringify(decision),
    }),

  getAirport: (code: string) => request<AirportConfig>(`/api/airports/${code}`),

  getBacktest: () => request<Record<string, any>>("/api/validation/backtest"),
};
