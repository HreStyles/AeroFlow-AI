// Category 8 — gate assignment, from the airport's real gate list, filtered
// to gates compatible with the selected aircraft type.
import { useMemo } from "react";
import type { AirportConfig, Flight } from "../../types/scenario";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  airport: AirportConfig | null;
  onChange: (patch: Partial<Flight>) => void;
}

export default function GateInput({ flight, airport, onChange }: Props) {
  const compatibleGates = useMemo(() => {
    if (!airport) return [];
    return airport.gates.filter((g) => {
      const compat = airport.gate_aircraft_compatibility[g];
      return !compat || compat.length === 0 || compat.includes(flight.aircraft_type);
    });
  }, [airport, flight.aircraft_type]);

  return (
    <>
      <Field
        label="Assigned gate"
        hint={
          airport
            ? `${compatibleGates.length} gates compatible with ${flight.aircraft_type}`
            : "loading airport gates…"
        }
      >
        <select
          className="aero-input"
          value={flight.assigned_gate}
          onChange={(e) => onChange({ assigned_gate: e.target.value })}
        >
          <option value="">— select —</option>
          {compatibleGates.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Gate next needed at" optional hint="when the next flight needs this gate">
        <input
          type="time"
          className="aero-input"
          value={flight.gate_next_needed_at ?? ""}
          onChange={(e) => onChange({ gate_next_needed_at: e.target.value || null })}
        />
      </Field>
    </>
  );
}
