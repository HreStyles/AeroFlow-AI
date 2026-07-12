// Mirrors backend SimEvent / EventLog / ValidationResults schemas
import type { CostModel, Flight } from "./scenario";
import type { RankedOption } from "./recommendations";

export type EventType =
  | "flight_departure"
  | "flight_arrival"
  | "gate_assignment"
  | "delay_predicted"
  | "cascade_detected"
  | "recommendation_generated"
  | "operator_decision"
  | "disruption_injected"
  | "gdp_started"
  | "gdp_ended";

export interface ShapFactor {
  feature: string;
  contribution: number;
}

export interface DelayPrediction {
  flight_id: string;
  probability: number;
  p10_minutes: number;
  p50_minutes: number;
  p90_minutes: number;
  confidence: number;
  shap_factors: ShapFactor[];
  prediction_source: string;
  provenance: Record<string, string>;
}

export interface GateConflict {
  gate: string;
  conflicting_flight: string;
  conflict_minutes: number;
}

export interface AffectedFlight {
  flight_id: string;
  propagated_delay_minutes: number;
  cause: string;
  from_tail: string;
}

export interface CascadeResult {
  trigger_flight: string;
  trigger_delay_minutes: number;
  affected_flights: AffectedFlight[];
  gate_conflicts: GateConflict[];
  missed_connections: number;
  total_downstream_delay_minutes: number;
  baseline_cost: number;
}

export interface RecommendationPayload {
  recommendation_id: string;
  trigger_flight: string;
  ranked_options: RankedOption[];
  optimality_gap_pct: number;
  solver_time_seconds: number;
  solver_status: string;
}

export interface SimEvent {
  sim_time: string; // "HH:MM:SS"
  event_type: EventType;
  flight_id: string | null;
  // Payload shape depends on event_type — cast at the point of use.
  details: Record<string, any>;
}

export interface SensitivityResult {
  stable_pct: number;
  fragile_ranges: { weight: string; factor: number; flips_to: string }[];
  perturbation?: string;
  base_recommendation?: string;
  note?: string;
}

export interface ValidationResults {
  optimality_gap_pct: number;
  baseline_costs: Record<string, number>;
  sensitivity: SensitivityResult;
  provenance_summary?: Record<string, number>;
}

export interface EventLog {
  scenario_id: string;
  scenario_name: string;
  airport_code: string;
  prediction_source: string;
  events: SimEvent[];
  validation: ValidationResults;
  flights: Flight[];
  provenance: Record<string, Record<string, string>>;
  cost_model?: CostModel;
}
