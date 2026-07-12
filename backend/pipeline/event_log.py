"""
EventLogBuilder — accumulates timestamped SimEvents and builds the final
EventLog JSON the frontend consumes. The event log is the single source of
truth for playback: the frontend never calls the pipeline during playback.
"""

EVENT_TYPES = {
    "flight_departure",
    "flight_arrival",
    "gate_assignment",
    "delay_predicted",
    "cascade_detected",
    "recommendation_generated",
    "operator_decision",
    "disruption_injected",
    "gdp_started",
    "gdp_ended",
}


def normalize_sim_time(sim_time: str) -> str:
    """Accept HH:MM or HH:MM:SS, always store HH:MM:SS."""
    parts = sim_time.split(":")
    if len(parts) == 2:
        return f"{sim_time}:00"
    return sim_time


class EventLogBuilder:
    def __init__(self, scenario_id: str, scenario_name: str = "",
                 airport_code: str = ""):
        self.scenario_id = scenario_id
        self.scenario_name = scenario_name
        self.airport_code = airport_code
        self.events: list[dict] = []

    def add_event(self, sim_time: str, event_type: str,
                  flight_id: str | None, details: dict) -> dict:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event_type '{event_type}'")
        event = {
            "sim_time": normalize_sim_time(sim_time),
            "event_type": event_type,
            "flight_id": flight_id,
            "details": details,
        }
        self.events.append(event)
        return event

    def build(self, validation: dict, flights: list[dict] | None = None,
              provenance: dict | None = None,
              prediction_source: str = "",
              cost_model: dict | None = None) -> dict:
        """Sort chronologically and assemble the final EventLog dict."""
        self.events.sort(key=lambda e: e["sim_time"])
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "airport_code": self.airport_code,
            "prediction_source": prediction_source,
            "events": self.events,
            "validation": validation,
            "flights": flights or [],
            "provenance": provenance or {},
            "cost_model": cost_model or {},
        }
