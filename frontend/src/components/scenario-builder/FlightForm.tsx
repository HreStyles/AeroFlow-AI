// Single-flight input form covering all 9 input categories.
import type { AirportConfig, Flight } from "../../types/scenario";
import {
  AIRCRAFT_TYPES,
  AIRPORTS,
  CARRIERS,
  SIMULATED_AIRPORTS,
} from "../../utils/aviation";
import { Field, Section } from "./fields";
import WeatherInput from "./WeatherInput";
import CongestionInput from "./CongestionInput";
import PassengerInput from "./PassengerInput";
import CrewInput from "./CrewInput";
import GateInput from "./GateInput";
import DisruptionInjector from "./DisruptionInjector";

interface Props {
  flight: Flight;
  index: number;
  airport: AirportConfig | null;
  scenarioAirport: string;
  onChange: (patch: Partial<Flight>) => void;
  onRemove: () => void;
  removable: boolean;
}

export default function FlightForm({
  flight,
  index,
  airport,
  scenarioAirport,
  onChange,
  onRemove,
  removable,
}: Props) {
  const setCarrier = (code: string) => {
    const patch: Partial<Flight> = { carrier_code: code };
    patch.flight_id = `${code}${flight.flight_number || ""}`;
    onChange(patch);
  };
  const setFlightNumber = (n: number) => {
    onChange({ flight_number: n, flight_id: `${flight.carrier_code}${n || ""}` });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">
          Flight {index + 1}
          {flight.flight_id && (
            <span className="font-mono text-aero-blue ml-2">{flight.flight_id}</span>
          )}
        </h3>
        {removable && (
          <button
            type="button"
            onClick={onRemove}
            className="text-xs text-aero-red hover:underline"
          >
            Remove flight
          </button>
        )}
      </div>

      <Section n={1} title="Flight identification">
        <Field label="Carrier">
          <select
            className="aero-input"
            value={flight.carrier_code}
            onChange={(e) => setCarrier(e.target.value)}
          >
            {Object.entries(CARRIERS).map(([code, name]) => (
              <option key={code} value={code}>
                {code} — {name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Flight number">
          <input
            type="number"
            min={1}
            max={9999}
            className="aero-input"
            value={flight.flight_number || ""}
            onChange={(e) => setFlightNumber(Number(e.target.value))}
          />
        </Field>
        <Field label="Tail number">
          <input
            type="text"
            className="aero-input font-mono"
            placeholder="N674DL"
            value={flight.tail_number}
            onChange={(e) => onChange({ tail_number: e.target.value.toUpperCase() })}
          />
        </Field>
        <Field label="Date">
          <input
            type="date"
            className="aero-input"
            value={flight.flight_date}
            onChange={(e) => onChange({ flight_date: e.target.value })}
          />
        </Field>
        <Field label="Origin" hint="scenario airport must be origin or destination">
          <select
            className="aero-input"
            value={flight.origin}
            onChange={(e) => onChange({ origin: e.target.value })}
          >
            {AIRPORTS.map((a) => (
              <option key={a} value={a}>
                {a}
                {SIMULATED_AIRPORTS.includes(a) ? " ★" : ""}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Destination">
          <select
            className="aero-input"
            value={flight.destination}
            onChange={(e) => onChange({ destination: e.target.value })}
          >
            {AIRPORTS.map((a) => (
              <option key={a} value={a}>
                {a}
                {SIMULATED_AIRPORTS.includes(a) ? " ★" : ""}
              </option>
            ))}
          </select>
        </Field>
      </Section>

      <Section n={2} title="Schedule">
        <Field label="Scheduled departure">
          <input
            type="time"
            className="aero-input"
            value={flight.scheduled_departure}
            onChange={(e) => onChange({ scheduled_departure: e.target.value })}
          />
        </Field>
        <Field label="Scheduled arrival">
          <input
            type="time"
            className="aero-input"
            value={flight.scheduled_arrival}
            onChange={(e) => onChange({ scheduled_arrival: e.target.value })}
          />
        </Field>
      </Section>

      <Section n={3} title="Aircraft">
        <Field label="Aircraft type">
          <select
            className="aero-input"
            value={flight.aircraft_type}
            onChange={(e) => onChange({ aircraft_type: e.target.value })}
          >
            {Object.keys(AIRCRAFT_TYPES).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Seating capacity" optional hint="auto-filled from type">
          <input
            type="number"
            className="aero-input"
            placeholder={String(AIRCRAFT_TYPES[flight.aircraft_type]?.capacity ?? "")}
            value={flight.seating_capacity ?? ""}
            onChange={(e) =>
              onChange({
                seating_capacity: e.target.value ? Number(e.target.value) : null,
              })
            }
          />
        </Field>
      </Section>

      <Section n={4} title="Weather">
        <WeatherInput flight={flight} onChange={onChange} />
      </Section>

      <Section n={5} title="Congestion">
        <CongestionInput flight={flight} onChange={onChange} />
      </Section>

      <Section n={6} title="Passengers">
        <PassengerInput flight={flight} onChange={onChange} />
      </Section>

      <Section n={7} title="Crew">
        <CrewInput flight={flight} onChange={onChange} />
      </Section>

      <Section n={8} title={`Gate assignment at ${scenarioAirport}`}>
        <GateInput flight={flight} airport={airport} onChange={onChange} />
      </Section>

      <Section n={9} title="Disruption injection (testing)">
        <DisruptionInjector flight={flight} onChange={onChange} />
      </Section>
    </div>
  );
}
