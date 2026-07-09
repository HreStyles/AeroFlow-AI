// Runway rendering + activity indicator.
import type { RunwayLayout } from "../../types/scenario";

interface Props {
  runway: RunwayLayout;
  active?: boolean;
  gdpActive?: boolean;
}

export default function RunwayStatus({ runway, active, gdpActive }: Props) {
  const midX = (runway.x1 + runway.x2) / 2;
  const midY = (runway.y1 + runway.y2) / 2;
  const angle =
    (Math.atan2(runway.y2 - runway.y1, runway.x2 - runway.x1) * 180) / Math.PI;
  return (
    <g>
      <line
        x1={runway.x1}
        y1={runway.y1}
        x2={runway.x2}
        y2={runway.y2}
        stroke={gdpActive ? "#7f1d1d" : "#1e293b"}
        strokeWidth={14}
        strokeLinecap="round"
      />
      <line
        x1={runway.x1}
        y1={runway.y1}
        x2={runway.x2}
        y2={runway.y2}
        stroke={active ? "#3b82f6" : "#475569"}
        strokeWidth={1.5}
        strokeDasharray="10 8"
        opacity={0.9}
      />
      <text
        transform={`translate(${midX}, ${midY - 12}) rotate(${angle})`}
        textAnchor="middle"
        fontSize={9}
        fill={gdpActive ? "#ef4444" : "#64748b"}
        className="font-mono"
      >
        {runway.id}
        {gdpActive ? " · GDP" : ""}
      </text>
    </g>
  );
}
