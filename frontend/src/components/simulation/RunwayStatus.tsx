// Runway rendering: asphalt band, dashed centerline, threshold bars, and
// runway designators at both ends.
import type { RunwayLayout } from "../../types/scenario";

interface Props {
  runway: RunwayLayout;
  gdpActive?: boolean;
}

export default function RunwayStatus({ runway, gdpActive }: Props) {
  const { x1, y1, x2, y2 } = runway;
  const angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI;
  const len = Math.hypot(x2 - x1, y2 - y1);
  const ux = (x2 - x1) / len;
  const uy = (y2 - y1) / len;
  // perpendicular unit vector for threshold bars
  const px = -uy;
  const py = ux;
  const [name1, name2] = runway.id.split("/");

  const threshold = (cx: number, cy: number) => (
    <g>
      {[-4, -1.5, 1.5, 4].map((o) => (
        <line
          key={o}
          x1={cx + px * o - ux * 4}
          y1={cy + py * o - uy * 4}
          x2={cx + px * o + ux * 4}
          y2={cy + py * o + uy * 4}
          stroke="#8fa3bf"
          strokeWidth={1.6}
          opacity={0.55}
        />
      ))}
    </g>
  );

  return (
    <g>
      {/* asphalt */}
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={gdpActive ? "#3b1d24" : "#1a2333"} strokeWidth={16} strokeLinecap="butt" />
      <line x1={x1} y1={y1} x2={x2} y2={y2}
        stroke={gdpActive ? "#7f1d1d" : "#2c3a52"} strokeWidth={16.5}
        strokeLinecap="butt" fill="none" opacity={0.5} />
      {/* centerline */}
      <line
        x1={x1 + ux * 16} y1={y1 + uy * 16} x2={x2 - ux * 16} y2={y2 - uy * 16}
        stroke="#94a8c4" strokeWidth={1.2} strokeDasharray="9 9" opacity={0.5}
      />
      {threshold(x1 + ux * 8, y1 + uy * 8)}
      {threshold(x2 - ux * 8, y2 - uy * 8)}
      {/* designators at each end */}
      <text
        transform={`translate(${x1 - ux * 14}, ${y1 - uy * 14}) rotate(${angle})`}
        textAnchor="end" dominantBaseline="central" fontSize={10} fontWeight={600}
        fill={gdpActive ? "#f87171" : "#64748b"} className="font-mono"
      >
        {name1}
      </text>
      <text
        transform={`translate(${x2 + ux * 14}, ${y2 + uy * 14}) rotate(${angle})`}
        textAnchor="start" dominantBaseline="central" fontSize={10} fontWeight={600}
        fill={gdpActive ? "#f87171" : "#64748b"} className="font-mono"
      >
        {name2}
      </text>
    </g>
  );
}
