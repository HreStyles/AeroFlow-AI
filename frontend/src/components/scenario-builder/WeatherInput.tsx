// Category 4 — weather: simple severity sliders OR advanced METAR-style
// fields (visibility/wind/ceiling/precipitation) that override severity.
import { useState } from "react";
import type { Flight } from "../../types/scenario";
import { Field } from "./fields";

interface Props {
  flight: Flight;
  onChange: (patch: Partial<Flight>) => void;
}

export default function WeatherInput({ flight, onChange }: Props) {
  const [advanced, setAdvanced] = useState(false);

  return (
    <>
      <div className="col-span-2 md:col-span-4 flex items-center gap-3">
        <span className="text-xs text-aero-muted">Mode:</span>
        <button
          type="button"
          onClick={() => setAdvanced(false)}
          className={`text-xs px-2 py-0.5 rounded ${!advanced ? "bg-aero-blue text-white" : "text-aero-muted"}`}
        >
          Simple (severity index)
        </button>
        <button
          type="button"
          onClick={() => setAdvanced(true)}
          className={`text-xs px-2 py-0.5 rounded ${advanced ? "bg-aero-blue text-white" : "text-aero-muted"}`}
        >
          Advanced (METAR fields)
        </button>
      </div>

      <Field label={`Origin severity: ${flight.origin_weather_severity.toFixed(2)}`}>
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={flight.origin_weather_severity}
          onChange={(e) =>
            onChange({ origin_weather_severity: Number(e.target.value) })
          }
          className="w-full accent-blue-500"
        />
      </Field>
      <Field
        label={`Destination severity: ${flight.destination_weather_severity.toFixed(2)}`}
      >
        <input
          type="range"
          min={0}
          max={1}
          step={0.01}
          value={flight.destination_weather_severity}
          onChange={(e) =>
            onChange({ destination_weather_severity: Number(e.target.value) })
          }
          className="w-full accent-blue-500"
        />
      </Field>

      {advanced && (
        <>
          <Field label="Origin visibility (mi)" optional>
            <input
              type="number"
              step={0.5}
              min={0}
              className="aero-input"
              value={flight.origin_visibility_miles ?? ""}
              onChange={(e) =>
                onChange({
                  origin_visibility_miles: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
            />
          </Field>
          <Field label="Origin wind (kt)" optional>
            <input
              type="number"
              min={0}
              className="aero-input"
              value={flight.origin_wind_knots ?? ""}
              onChange={(e) =>
                onChange({
                  origin_wind_knots: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
          </Field>
          <Field label="Origin ceiling (ft)" optional>
            <input
              type="number"
              min={0}
              step={100}
              className="aero-input"
              value={flight.origin_ceiling_feet ?? ""}
              onChange={(e) =>
                onChange({
                  origin_ceiling_feet: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
            />
          </Field>
          <Field label="Origin precipitation" optional>
            <select
              className="aero-input"
              value={flight.origin_precipitation ?? "none"}
              onChange={(e) =>
                onChange({
                  origin_precipitation: e.target.value as Flight["origin_precipitation"],
                })
              }
            >
              {["none", "rain", "snow", "ice"].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </Field>
        </>
      )}
    </>
  );
}
