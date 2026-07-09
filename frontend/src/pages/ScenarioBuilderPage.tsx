// Custom scenario builder: multi-flight form (9 input categories per
// flight), provenance hints for estimated fields, validation, review step,
// then POST /api/simulate → simulation dashboard.
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import FlightForm from "../components/scenario-builder/FlightForm";
import ScenarioSummary from "../components/scenario-builder/ScenarioSummary";
import { api } from "../api/client";
import { useScenario } from "../hooks/useScenario";
import type { AirportConfig, Flight, Scenario } from "../types/scenario";
import { SIMULATED_AIRPORTS } from "../utils/aviation";

function blankFlight(airport: string): Flight {
  return {
    flight_id: "",
    carrier_code: "DL",
    flight_number: 0,
    tail_number: "",
    origin: airport === "ATL" ? "JFK" : "BOS",
    destination: airport,
    flight_date: new Date().toISOString().slice(0, 10),
    scheduled_departure: "12:00",
    scheduled_arrival: "14:30",
    aircraft_type: "A321",
    seating_capacity: null,
    origin_weather_severity: 0.2,
    destination_weather_severity: 0.2,
    origin_congestion: "moderate",
    destination_congestion: "moderate",
    total_passengers: null,
    connecting_passengers: null,
    avg_connection_buffer_min: null,
    crew_duty_start: null,
    crew_hours_on_duty: null,
    standby_crew_available: null,
    assigned_gate: "",
    gate_next_needed_at: null,
    injected_delay_cause: null,
    injected_delay_minutes: null,
    injected_delay_time: null,
  };
}

export default function ScenarioBuilderPage() {
  const [airportCode, setAirportCode] = useState("ATL");
  const [airportConfig, setAirportConfig] = useState<AirportConfig | null>(null);
  const [scenarioName, setScenarioName] = useState("Custom scenario");
  const [flights, setFlights] = useState<Flight[]>([blankFlight("ATL")]);
  const [reviewing, setReviewing] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const { submitScenario, loading, error, errorStatus, clearError } = useScenario();
  const navigate = useNavigate();

  useEffect(() => {
    api.getAirport(airportCode).then(setAirportConfig).catch(() => setAirportConfig(null));
  }, [airportCode]);

  const patchFlight = (index: number, patch: Partial<Flight>) =>
    setFlights((prev) =>
      prev.map((f, i) => (i === index ? { ...f, ...patch } : f))
    );

  const errors = useMemo(() => {
    const list: string[] = [];
    flights.forEach((f, i) => {
      const label = f.flight_id || `Flight ${i + 1}`;
      if (!f.flight_number) list.push(`${label}: flight number is required`);
      if (!/^N[0-9]{1,4}[A-Z]{0,3}$/.test(f.tail_number))
        list.push(`${label}: tail number must look like N674DL`);
      if (!f.assigned_gate) list.push(`${label}: assigned gate is required`);
      if (f.origin === f.destination) list.push(`${label}: origin equals destination`);
      if (f.origin !== airportCode && f.destination !== airportCode)
        list.push(`${label}: must touch scenario airport ${airportCode}`);
      if (f.scheduled_departure >= f.scheduled_arrival && f.destination !== f.origin)
        list.push(`${label}: arrival must be after departure`);
    });
    const ids = flights.map((f) => f.flight_id);
    if (new Set(ids).size !== ids.length)
      list.push("Flight IDs must be unique (carrier + number)");
    return list;
  }, [flights, airportCode]);

  const submit = async () => {
    setValidationErrors(errors);
    if (errors.length) {
      setReviewing(false);
      return;
    }
    const scenario: Scenario = {
      scenario_id: `custom_${Date.now()}`,
      scenario_name: scenarioName,
      airport: airportCode,
      flights,
      gdp_events: [],
      cost_weights: null,
      description: "Custom scenario built in the UI",
    };
    const log = await submitScenario(scenario);
    if (log) navigate("/simulate");
  };

  return (
    <PageLayout>
      <div className="max-w-4xl mx-auto p-6 space-y-4">
        <div>
          <h1 className="text-xl font-bold">Build a custom scenario</h1>
          <p className="text-sm text-aero-muted">
            The live pipeline (prediction → simulation → MILP optimization)
            runs on submit. Optional fields left blank are estimated with
            disclosed statistical defaults — never silently invented.
          </p>
        </div>

        <div className="aero-card p-3 grid grid-cols-2 md:grid-cols-3 gap-3">
          <label className="block">
            <span className="aero-label mb-1 block">Scenario name</span>
            <input
              className="aero-input"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="aero-label mb-1 block">Airport (simulated)</span>
            <select
              className="aero-input"
              value={airportCode}
              onChange={(e) => setAirportCode(e.target.value)}
            >
              {SIMULATED_AIRPORTS.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </label>
        </div>

        {!reviewing &&
          flights.map((f, i) => (
            <div key={i} className="aero-card p-4">
              <FlightForm
                flight={f}
                index={i}
                airport={airportConfig}
                scenarioAirport={airportCode}
                onChange={(patch) => patchFlight(i, patch)}
                onRemove={() =>
                  setFlights((prev) => prev.filter((_, j) => j !== i))
                }
                removable={flights.length > 1}
              />
            </div>
          ))}

        {!reviewing && (
          <button
            type="button"
            onClick={() => setFlights((prev) => [...prev, blankFlight(airportCode)])}
            className="aero-btn w-full border-dashed"
          >
            + Add flight (multi-flight scenarios enable rotation cascades)
          </button>
        )}

        {reviewing && <ScenarioSummary flights={flights} airportCode={airportCode} />}

        {(validationErrors.length > 0 || errors.length > 0) && reviewing === false && validationErrors.length > 0 && (
          <div className="rounded border border-red-500/40 bg-red-500/10 text-aero-red text-xs px-4 py-3 space-y-0.5">
            {validationErrors.map((e, i) => (
              <div key={i}>• {e}</div>
            ))}
          </div>
        )}

        {error && (
          <div
            className={`rounded border text-sm px-4 py-3 ${
              errorStatus === 503
                ? "border-amber-500/40 bg-amber-500/10 text-aero-amber"
                : "border-red-500/40 bg-red-500/10 text-aero-red"
            }`}
            data-testid="submit-error"
          >
            <div className="font-semibold mb-1">
              {errorStatus === 503 ? "Model not trained" : "Scenario rejected"}
            </div>
            {error}
            <button onClick={clearError} className="block mt-2 underline text-xs">
              dismiss
            </button>
          </div>
        )}

        <div className="flex gap-3">
          {!reviewing ? (
            <button
              type="button"
              onClick={() => {
                setValidationErrors(errors);
                if (!errors.length) setReviewing(true);
              }}
              className="aero-btn-primary"
            >
              Review scenario →
            </button>
          ) : (
            <>
              <button type="button" onClick={() => setReviewing(false)} className="aero-btn">
                ← Edit
              </button>
              <button
                type="button"
                onClick={submit}
                disabled={loading}
                className="aero-btn-primary"
                data-testid="run-simulation"
              >
                {loading ? "Running live pipeline…" : "Run simulation"}
              </button>
            </>
          )}
        </div>
      </div>
    </PageLayout>
  );
}
