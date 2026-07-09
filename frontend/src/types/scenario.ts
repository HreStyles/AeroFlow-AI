// Mirrors backend/api/schemas.py (Pydantic models)

export type CongestionLevel = "low" | "moderate" | "high" | "severe";
export type Precipitation = "none" | "rain" | "snow" | "ice";
export type DelayCause =
  | "weather"
  | "mechanical"
  | "atc_ground_stop"
  | "late_aircraft"
  | "crew";

export interface Flight {
  // Category 1 — identification (required)
  flight_id: string;
  carrier_code: string;
  flight_number: number;
  tail_number: string;
  origin: string;
  destination: string;
  flight_date: string;
  // Category 2 — schedule (required)
  scheduled_departure: string;
  scheduled_arrival: string;
  // Category 3 — aircraft
  aircraft_type: string;
  seating_capacity?: number | null;
  rotation_position?: number | null;
  // Category 4 — weather
  origin_weather_severity: number;
  destination_weather_severity: number;
  origin_visibility_miles?: number | null;
  origin_wind_knots?: number | null;
  origin_ceiling_feet?: number | null;
  origin_precipitation?: Precipitation | null;
  destination_visibility_miles?: number | null;
  destination_wind_knots?: number | null;
  destination_ceiling_feet?: number | null;
  destination_precipitation?: Precipitation | null;
  // Category 5 — congestion
  origin_congestion: CongestionLevel;
  destination_congestion: CongestionLevel;
  // Category 6 — passengers (assumed-with-disclosure when omitted)
  total_passengers?: number | null;
  connecting_passengers?: number | null;
  avg_connection_buffer_min?: number | null;
  // Category 7 — crew
  crew_duty_start?: string | null;
  crew_hours_on_duty?: number | null;
  standby_crew_available?: boolean | null;
  // Category 8 — gate
  assigned_gate: string;
  gate_next_needed_at?: string | null;
  // Category 9 — disruption injection
  injected_delay_cause?: DelayCause | null;
  injected_delay_minutes?: number | null;
  injected_delay_time?: string | null;
  // Fleet status ("idle" = spare aircraft)
  status?: string | null;
  // Derived fields returned by the completeness layer
  assigned_runway?: string;
  wake_category?: string;
  body_type?: string;
  estimated_deplaning_minutes?: number;
  estimated_boarding_minutes?: number;
}

export interface CostWeights {
  passenger_delay_per_minute: number;
  missed_connection_per_pax: number;
  crew_overtime_per_hour: number;
  gate_conflict_penalty: number;
  aircraft_swap_cost: number;
  fuel_taxi_per_minute: number;
}

export interface GDPEvent {
  airport: string;
  start_time: string;
  end_time: string;
  reduced_acceptance_rate: number;
}

export interface RunwayLayout {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface GatePosition {
  id: string;
  x: number;
  y: number;
}

export interface ConcourseLayout {
  id: string;
  x: number;
  y: number;
  gates: string[];
  gate_positions?: GatePosition[];
}

export interface MapLayout {
  width: number;
  height: number;
  runways: RunwayLayout[];
  concourses: ConcourseLayout[];
  taxiways?: { id: string; points: number[][] }[];
}

export interface AirportConfig {
  airport_code: string;
  airport_name: string;
  gates: string[];
  gate_aircraft_compatibility: Record<string, string[]>;
  runways: string[];
  runway_configs: Record<string, Record<string, unknown>>;
  vmc_capacity_per_hour: number;
  imc_capacity_per_hour: number;
  min_turnaround_minutes: Record<string, number>;
  map_layout?: MapLayout;
}

export interface Scenario {
  scenario_id: string;
  scenario_name: string;
  airport: string | AirportConfig;
  flights: Flight[];
  gdp_events: GDPEvent[];
  cost_weights?: CostWeights | null;
  description?: string | null;
}

export interface PresetSummary {
  id: string;
  name: string;
  description: string;
  airport: string;
  flight_count: number;
  gdp_event_count: number;
}
