// Small colored tag showing data provenance next to any value:
//   green  "Provided"  — user entered this
//   blue   "Derived"   — computed from other known fields
//   amber  "Estimated" — statistically assumed, tooltip shows the method
interface Props {
  provenance: string; // "user_provided" | "derived" | "assumed_default (…)"
  compact?: boolean;
}

export default function ProvenanceBadge({ provenance, compact }: Props) {
  const kind = provenance.split(" ")[0];
  const config =
    kind === "user_provided"
      ? { label: "Provided", cls: "bg-green-500/15 text-aero-green border-green-500/30" }
      : kind === "derived"
        ? { label: "Derived", cls: "bg-blue-500/15 text-aero-blue border-blue-500/30" }
        : { label: "Estimated", cls: "bg-amber-500/15 text-aero-amber border-amber-500/30" };

  const method = provenance.includes("(")
    ? provenance.slice(provenance.indexOf("(") + 1, provenance.lastIndexOf(")"))
    : null;

  return (
    <span
      title={method ? `Assumed from: ${method}` : config.label}
      className={`inline-block border rounded px-1 py-px font-medium leading-none ${
        compact ? "text-[8px]" : "text-[10px]"
      } ${config.cls}`}
    >
      {config.label}
    </span>
  );
}
