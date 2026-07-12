// One aircraft on the map, colored by status:
//   green = on time, amber = predicted delay, red = delayed/disrupted
interface Props {
  x: number;
  y: number;
  rotation: number;
  status: "normal" | "warning" | "disrupted";
  label: string;
  isSpare?: boolean;
  highlighted?: boolean;
  opacity?: number;
  moving?: boolean;
}

const COLORS = { normal: "#22c55e", warning: "#f59e0b", disrupted: "#ef4444" };

export default function AircraftIcon({
  x,
  y,
  rotation,
  status,
  label,
  isSpare,
  highlighted,
  opacity = 1,
  moving,
}: Props) {
  const color = isSpare ? "#64748b" : COLORS[status];
  return (
    <g transform={`translate(${x}, ${y})`} opacity={opacity}>
      {/* motion trail while taxiing */}
      {moving && (
        <line
          x1={0}
          y1={0}
          x2={-Math.cos((rotation * Math.PI) / 180) * 26}
          y2={-Math.sin((rotation * Math.PI) / 180) * 26}
          stroke={color}
          strokeWidth={2.5}
          strokeLinecap="round"
          opacity={0.25}
        />
      )}
      {highlighted && (
        <circle r={16} fill="none" stroke={color} strokeWidth={1.5} opacity={0.8}>
          <animate attributeName="r" values="13;20;13" dur="1.8s" repeatCount="indefinite" />
          <animate attributeName="opacity" values="0.8;0.15;0.8" dur="1.8s" repeatCount="indefinite" />
        </circle>
      )}
      {/* soft shadow */}
      <g transform={`rotate(${rotation + 90}) scale(1.5)`} opacity={0.35}>
        <path
          d="M0,-9 L2.2,-3 L8,1.5 L8,4 L2,2 L1.5,7 L4,9.5 L4,11 L0,10 L-4,11 L-4,9.5 L-1.5,7 L-2,2 L-8,4 L-8,1.5 L-2.2,-3 Z"
          fill="#000"
          transform="translate(0.8, 1.2)"
        />
      </g>
      <g transform={`rotate(${rotation + 90}) scale(1.5)`}>
        <path
          d="M0,-9 L2.2,-3 L8,1.5 L8,4 L2,2 L1.5,7 L4,9.5 L4,11 L0,10 L-4,11 L-4,9.5 L-1.5,7 L-2,2 L-8,4 L-8,1.5 L-2.2,-3 Z"
          fill={color}
          stroke="#0a0f1a"
          strokeWidth={0.5}
        />
      </g>
      <g>
        <rect
          x={-label.length * 3.6 - 4}
          y={-27}
          width={label.length * 7.2 + 8}
          height={13}
          rx={3}
          fill="#0a0f1a"
          opacity={0.75}
        />
        <text
          y={-17.5}
          textAnchor="middle"
          fontSize={10}
          fontWeight={600}
          className="font-mono"
          fill={color}
        >
          {label}
        </text>
      </g>
    </g>
  );
}
