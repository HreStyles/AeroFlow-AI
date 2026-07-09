// Horizontal strip of clickable event markers — jump-to-event playback control.
import type { TimelineMarker } from "../../hooks/useEventLog";

interface Props {
  markers: TimelineMarker[];
  progressPct: number;
  onJump: (eventIndex: number) => void;
}

const MARKER_STYLE: Record<string, { color: string; symbol: string; label: string }> = {
  disruption_injected: { color: "#ef4444", symbol: "⚡", label: "Disruption" },
  delay_predicted: { color: "#f59e0b", symbol: "◆", label: "Delay predicted" },
  cascade_detected: { color: "#ef4444", symbol: "▲", label: "Cascade" },
  recommendation_generated: { color: "#3b82f6", symbol: "●", label: "AI recommendation" },
  gdp_started: { color: "#a855f7", symbol: "▮", label: "GDP start" },
  gdp_ended: { color: "#a855f7", symbol: "▯", label: "GDP end" },
};

export default function EventTimeline({ markers, progressPct, onJump }: Props) {
  return (
    <div className="aero-card px-4 py-2">
      <div className="flex items-center justify-between mb-1">
        <span className="aero-label">Event timeline</span>
        <div className="flex gap-3">
          {Object.entries(MARKER_STYLE).slice(0, 4).map(([k, v]) => (
            <span key={k} className="text-[10px] text-aero-muted">
              <span style={{ color: v.color }}>{v.symbol}</span> {v.label}
            </span>
          ))}
        </div>
      </div>
      <div className="relative h-8">
        {/* track */}
        <div className="absolute top-1/2 left-0 right-0 h-1 -mt-0.5 rounded bg-aero-border" />
        {/* progress */}
        <div
          className="absolute top-1/2 left-0 h-1 -mt-0.5 rounded bg-aero-blue/60 transition-all"
          style={{ width: `${progressPct}%` }}
        />
        {/* playhead */}
        <div
          className="absolute top-0 bottom-0 w-px bg-aero-blue"
          style={{ left: `${progressPct}%` }}
        />
        {/* markers */}
        {markers.map((m) => {
          const style = MARKER_STYLE[m.event.event_type];
          if (!style) return null;
          return (
            <button
              key={m.event.index}
              onClick={() => onJump(m.event.index)}
              title={`${m.event.sim_time} — ${style.label}${
                m.event.flight_id ? ` (${m.event.flight_id})` : ""
              }`}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 text-xs leading-none hover:scale-150 transition-transform"
              style={{
                left: `${m.positionPct}%`,
                color: style.color,
                opacity: m.fired ? 1 : 0.35,
              }}
            >
              {style.symbol}
            </button>
          );
        })}
      </div>
    </div>
  );
}
