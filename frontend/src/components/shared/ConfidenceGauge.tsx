// Circular confidence indicator (SVG arc).
interface Props {
  value: number; // 0–1
  size?: number;
  label?: string;
}

export default function ConfidenceGauge({ value, size = 72, label = "Confidence" }: Props) {
  const clamped = Math.max(0, Math.min(1, value));
  const r = size / 2 - 6;
  const circumference = 2 * Math.PI * r;
  const color =
    clamped >= 0.7 ? "#22c55e" : clamped >= 0.4 ? "#f59e0b" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#1e293b"
          strokeWidth={6}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - clamped)}
        />
        <text
          x={size / 2}
          y={size / 2}
          textAnchor="middle"
          dominantBaseline="central"
          className="rotate-90 font-mono font-bold"
          style={{ transformOrigin: "center" }}
          fill={color}
          fontSize={size / 4.5}
        >
          {Math.round(clamped * 100)}%
        </text>
      </svg>
      <span className="aero-label">{label}</span>
    </div>
  );
}
