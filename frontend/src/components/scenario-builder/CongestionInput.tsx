// Category 5 — congestion levels.
import type { Flight } from "../../types/scenario";
import { CONGESTION_LEVELS } from "../../utils/aviation";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  onChange: (patch: Partial<Flight>) => void;
}

export default function CongestionInput({ flight, onChange }: Props) {
  return (
    <>
      <Field label="Origin congestion">
        <select
          className="aero-input"
          value={flight.origin_congestion}
          onChange={(e) =>
            onChange({ origin_congestion: e.target.value as Flight["origin_congestion"] })
          }
        >
          {CONGESTION_LEVELS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Destination congestion">
        <select
          className="aero-input"
          value={flight.destination_congestion}
          onChange={(e) =>
            onChange({
              destination_congestion: e.target.value as Flight["destination_congestion"],
            })
          }
        >
          {CONGESTION_LEVELS.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </Field>
    </>
  );
}
