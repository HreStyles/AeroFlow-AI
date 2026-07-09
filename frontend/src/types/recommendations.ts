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
  expected_cost: number;
  cost_reduction_pct: number;
  delay_impact_minutes: number;
  downstream_impact: "low" | "medium" | "high";
  success_probability: number;
  optimality_gap_pct: number;
  feasibility_checks: FeasibilityChecks;
  rationale: string[];
}

export interface OperatorDecisionRecord {
  recommendation_id: string;
  selected_rank: number;
  decision: "accepted" | "overridden";
  override_reason?: string | null;
}
