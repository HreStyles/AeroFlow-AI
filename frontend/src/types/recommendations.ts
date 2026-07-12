export interface FeasibilityChecks {
  gate_compatible: boolean;
  aircraft_type_match: boolean;
  crew_legal: boolean;
}

export interface RankedOption {
  rank: number;
  action: string;
  action_type: string;
  action_details: Record<string, any>;
  /** Weighted expected cost over the P10/P50/P90 delay outcomes
   *  (0.25 / 0.50 / 0.25 three-point quadrature). */
  expected_cost: number;
  expected_cost_p10: number;
  expected_cost_p50: number;
  expected_cost_p90: number;
  cost_reduction_pct: number;
  delay_impact_minutes: number;
  downstream_impact: "low" | "medium" | "high";
  optimality_gap_pct: number;
  feasibility_checks: FeasibilityChecks;
  rationale: string[];
}

export interface EvaluationInfo {
  method: string;
  quantile_weights: Record<string, number>;
  quantile_delays_minutes: Record<string, number>;
  expected_baseline_cost: number;
  feasibility_checked_at: string;
}

export interface OperatorDecisionRecord {
  recommendation_id: string;
  selected_rank: number;
  decision: "accepted" | "overridden";
  override_reason?: string | null;
}
