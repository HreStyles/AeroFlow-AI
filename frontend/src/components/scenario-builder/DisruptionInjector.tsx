// Category 9 — chaos injection controls (testing only).
import type { Flight } from "../../types/scenario";
import { DELAY_CAUSES } from "../../utils/aviation";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  onChange: (patch: Partial<Flight>) => void;
}

export default function DisruptionInjector({ flight, onChange }: Props) {
  const active = !!flight.injected_delay_cause;
  return (
    <>
      <Field label="Inject disruption" optional>
        <select
          className="aero-input"
          value={flight.injected_delay_cause ?? ""}
          onChange={(e) =>
            onChange({
              injected_delay_cause: (e.target.value || null) as Flight["injected_delay_cause"],
              ...(e.target.value
                ? {}
                : { injected_delay_minutes: null, injected_delay_time: null }),
            })
          }
        >
          <option value="">none</option>
          {DELAY_CAUSES.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </Field>
      {active && (
        <>
          <Field label="Delay minutes">
            <input
              type="number"
              min={5}
              max={360}
              className="aero-input"
              value={flight.injected_delay_minutes ?? 30}
              onChange={(e) =>
                onChange({ injected_delay_minutes: Number(e.target.value) })
              }
            />
          </Field>
          <Field label="Fires at" optional hint="blank → at scheduled departure">
            <input
              type="time"
              className="aero-input"
              value={flight.injected_delay_time ?? ""}
              onChange={(e) =>
                onChange({ injected_delay_time: e.target.value || null })
              }
            />
          </Field>
        </>
      )}
    </>
  );
}
