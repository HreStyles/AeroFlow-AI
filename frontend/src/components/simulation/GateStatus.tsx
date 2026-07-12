// Gate stub + occupancy state on a concourse pier.
interface Props {
  x: number;
  y: number;
  gate: string;
  occupied: boolean;
  conflict?: boolean;
  highlight?: boolean;
}

export default function GateStatus({ x, y, gate, occupied, conflict, highlight }: Props) {
  const color = conflict ? "#ef4444" : highlight ? "#3b82f6" : occupied ? "#3b82f6" : "#2b3a52";
  return (
    <g transform={`translate(${x}, ${y})`}>
      {/* jet-bridge stub from the pier down to the stand */}
      <line x1={0} y1={-14} x2={0} y2={-6} stroke="#2b3a52" strokeWidth={2} />
      <rect
        x={-4}
        y={-7}
        width={8}
        height={6}
        rx={1.5}
        fill={color}
        opacity={occupied || conflict || highlight ? 1 : 0.55}
        className={conflict ? "animate-pulse-alert" : undefined}
      />
      {highlight && (
        <circle cy={-4} r={9} fill="none" stroke="#3b82f6" strokeWidth={1.2}
          strokeDasharray="3 2" className="animate-pulse-alert" />
      )}
      <text
        y={11}
        textAnchor="middle"
        fontSize={7.5}
        fill={conflict ? "#f87171" : highlight ? "#93c5fd" : "#5c6f8a"}
        className="font-mono"
        fontWeight={conflict || highlight ? 700 : 400}
      >
        {gate}
      </text>
    </g>
  );
}
