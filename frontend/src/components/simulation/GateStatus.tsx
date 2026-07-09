// Gate occupancy indicator on the map: a small tick per gate, highlighted
// when occupied or involved in a conflict/reassignment.
interface Props {
  x: number;
  y: number;
  gate: string;
  occupied: boolean;
  conflict?: boolean;
  highlight?: boolean;
}

export default function GateStatus({ x, y, gate, occupied, conflict, highlight }: Props) {
  const color = conflict ? "#ef4444" : occupied ? "#3b82f6" : "#334155";
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect
        x={-3}
        y={-10}
        width={6}
        height={8}
        rx={1}
        fill={color}
        opacity={occupied || conflict ? 0.95 : 0.6}
        className={conflict ? "animate-pulse-alert" : undefined}
      />
      <text
        y={10}
        textAnchor="middle"
        fontSize={7.5}
        fill={highlight ? "#e2e8f0" : "#64748b"}
        className="font-mono"
      >
        {gate}
      </text>
    </g>
  );
}
