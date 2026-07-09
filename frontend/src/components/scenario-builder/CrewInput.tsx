// Category 7 — crew. Optional with disclosed defaults.
import type { Flight } from "../../types/scenario";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  onChange: (patch: Partial<Flight>) => void;
}

export default function CrewInput({ flight, onChange }: Props) {
  return (
    <>
      <Field label="Crew duty start" optional hint="blank → 2h before departure">
        <input
          type="time"
          className="aero-input"
          value={flight.crew_duty_start ?? ""}
          onChange={(e) => onChange({ crew_duty_start: e.target.value || null })}
        />
      </Field>
      <Field label="Hours on duty" optional>
        <input
          type="number"
          min={0}
          max={16}
          step={0.5}
          className="aero-input"
          placeholder="estimated"
          value={flight.crew_hours_on_duty ?? ""}
          onChange={(e) =>
            onChange({
              crew_hours_on_duty: e.target.value ? Number(e.target.value) : null,
            })
          }
        />
      </Field>
      <Field label="Standby crew available" optional hint="blank → assumed yes">
        <select
          className="aero-input"
          value={
            flight.standby_crew_available === null ||
            flight.standby_crew_available === undefined
              ? ""
              : String(flight.standby_crew_available)
          }
          onChange={(e) =>
            onChange({
              standby_crew_available:
                e.target.value === "" ? null : e.target.value === "true",
            })
          }
        >
          <option value="">assume default</option>
          <option value="true">yes</option>
          <option value="false">no</option>
        </select>
      </Field>
    </>
  );
}
