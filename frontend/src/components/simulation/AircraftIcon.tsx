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
}: Props) {
  const color = isSpare ? "#64748b" : COLORS[status];
  return (
    <g transform={`translate(${x}, ${y})`} opacity={opacity}>
      {highlighted && (
        <circle r={16} fill="none" stroke={color} strokeWidth={1.5} opacity={0.7}>
          <animate
            attributeName="r"
            values="12;18;12"
            dur="1.6s"
            repeatCount="indefinite"
          />
        </circle>
      )}
      <g transform={`rotate(${rotation + 90}) scale(1.5)`}>
        {/* simple plane silhouette pointing "up" pre-rotation */}
        <path
          d="M0,-9 L2.2,-3 L8,1.5 L8,4 L2,2 L1.5,7 L4,9.5 L4,11 L0,10 L-4,11 L-4,9.5 L-1.5,7 L-2,2 L-8,4 L-8,1.5 L-2.2,-3 Z"
          fill={color}
          stroke="#0a0f1a"
          strokeWidth={0.5}
        />
      </g>
      <text
        y={-18}
        textAnchor="middle"
        fontSize={11}
        fontWeight={600}
        className="font-mono"
        fill={color}
      >
        {label}
      </text>
    </g>
  );
}
