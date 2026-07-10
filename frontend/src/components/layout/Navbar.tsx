import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { api, type HealthStatus } from "../../api/client";

const links = [
  { to: "/simulate", label: "Simulate" },
  { to: "/build", label: "Build Scenario" },
  { to: "/presets", label: "Presets" },
  { to: "/validation", label: "Validation" },
];

export default function Navbar({ right }: { right?: ReactNode }) {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [down, setDown] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setDown(true));
  }, []);

  return (
    <nav className="h-12 flex items-center gap-5 px-4 border-b border-aero-border bg-aero-card/90 backdrop-blur shrink-0">
      <NavLink to="/" className="flex items-center gap-2 shrink-0">
        <span className="w-7 h-7 rounded-md bg-aero-blue/15 border border-aero-blue/30 flex items-center justify-center text-aero-blue text-sm">
          ✈
        </span>
        <span className="font-bold tracking-tight leading-none">
          AeroFlow <span className="text-aero-blue">AI</span>
          <span className="block text-[8px] font-semibold tracking-[0.2em] text-aero-muted mt-0.5">
            AOCC DECISION SUPPORT
          </span>
        </span>
      </NavLink>

      <div className="flex items-center gap-0.5">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-md text-[13px] transition-colors whitespace-nowrap ${
                isActive
                  ? "bg-aero-blue/15 text-aero-blue font-semibold"
                  : "text-aero-muted hover:text-aero-text hover:bg-white/[0.03]"
              }`
            }
          >
            {l.label}
          </NavLink>
        ))}
      </div>

      {/* live system status */}
      <div className="hidden xl:flex items-center gap-1.5 ml-1">
        {down ? (
          <span className="status-chip border-red-500/40 text-aero-red bg-red-500/10">
            <span className="w-1.5 h-1.5 rounded-full bg-aero-red animate-pulse-alert" />
            BACKEND OFFLINE
          </span>
        ) : health ? (
          <span
            className={`status-chip ${
              health.model_trained
                ? "border-green-500/30 text-aero-green bg-green-500/10"
                : "border-amber-500/30 text-aero-amber bg-amber-500/10"
            }`}
            title={`prediction source: ${health.prediction_source}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${health.model_trained ? "bg-aero-green" : "bg-aero-amber"}`} />
            {health.model_trained ? "LIGHTGBM LIVE" : "HEURISTIC MODE"}
          </span>
        ) : null}
      </div>

      <div className="ml-auto flex items-center gap-3">{right}</div>
    </nav>
  );
}
