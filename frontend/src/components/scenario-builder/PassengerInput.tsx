// Category 6 — passengers. All optional: blank fields show a "will be
// estimated" provenance hint (load factor / DB1B connection-rate defaults).
import type { Flight } from "../../types/scenario";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  onChange: (patch: Partial<Flight>) => void;
}

export default function PassengerInput({ flight, onChange }: Props) {
  const num = (v: string) => (v === "" ? null : Number(v));
  return (
    <>
      <Field label="Total passengers" optional hint="blank → capacity × 0.84 load factor">
        <input
          type="number"
          min={0}
          className="aero-input"
          placeholder="estimated"
          value={flight.total_passengers ?? ""}
          onChange={(e) => onChange({ total_passengers: num(e.target.value) })}
        />
      </Field>
      <Field label="Connecting passengers" optional hint="blank → 30% hub connection rate">
        <input
          type="number"
          min={0}
          className="aero-input"
          placeholder="estimated"
          value={flight.connecting_passengers ?? ""}
          onChange={(e) => onChange({ connecting_passengers: num(e.target.value) })}
        />
      </Field>
      <Field label="Avg connection buffer (min)" optional hint="blank → 55 min typical MCT">
        <input
          type="number"
          min={0}
          className="aero-input"
          placeholder="estimated"
          value={flight.avg_connection_buffer_min ?? ""}
          onChange={(e) =>
            onChange({ avg_connection_buffer_min: num(e.target.value) })
          }
        />
      </Field>
    </>
  );
}
