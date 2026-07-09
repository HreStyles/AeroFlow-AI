import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";

const links = [
  { to: "/simulate", label: "Simulate" },
  { to: "/build", label: "Build Scenario" },
  { to: "/presets", label: "Presets" },
  { to: "/validation", label: "Validation" },
];

export default function Navbar({ right }: { right?: ReactNode }) {
  return (
    <nav className="h-12 flex items-center gap-6 px-4 border-b border-aero-border bg-aero-card shrink-0">
      <NavLink to="/" className="flex items-center gap-2 shrink-0">
        <span className="text-aero-blue text-lg">✈</span>
        <span className="font-bold tracking-tight">
          AeroFlow <span className="text-aero-blue">AI</span>
        </span>
        <span className="aero-label hidden md:inline">AOCC Decision Support</span>
      </NavLink>
      <div className="flex items-center gap-1">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm transition-colors ${
                isActive
                  ? "bg-aero-blue/15 text-aero-blue font-medium"
                  : "text-aero-muted hover:text-aero-text"
              }`
            }
          >
            {l.label}
          </NavLink>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-3">{right}</div>
    </nav>
  );
}
