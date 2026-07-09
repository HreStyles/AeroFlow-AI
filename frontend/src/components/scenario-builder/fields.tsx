// Small shared form primitives for the scenario builder.
import type { ReactNode } from "react";
import ProvenanceBadge from "../shared/ProvenanceBadge";

export function Field({
  label,
  children,
  optional,
  hint,
}: {
  label: string;
  children: ReactNode;
  optional?: boolean;
  hint?: string;
}) {
  return (
    <label className="block">
      <span className="aero-label flex items-center gap-1.5 mb-1">
        {label}
        {optional && <ProvenanceBadge provenance="assumed_default (will be estimated)" compact />}
      </span>
      {children}
      {hint && <span className="text-[10px] text-aero-muted">{hint}</span>}
    </label>
  );
}

export function Section({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children: ReactNode;
}) {
  return (
    <fieldset className="aero-card p-3">
      <legend className="aero-label px-1">
        <span className="text-aero-blue font-mono">{n}</span> · {title}
      </legend>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">{children}</div>
    </fieldset>
  );
}
