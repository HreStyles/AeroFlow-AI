// Horizontal strip of clickable event markers with an hour axis —
// jump-to-event playback control.
import { useMemo } from "react";
import type { TimelineMarker } from "../../hooks/useEventLog";
import { secondsToHHMM } from "../../utils/formatting";

interface Props {
  markers: TimelineMarker[];
  progressPct: number;
  startTime: number;
  endTime: number;
  simTime: number;
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

export default function EventTimeline({
  markers, progressPct, startTime, endTime, simTime, onJump,
}: Props) {
  const hourTicks = useMemo(() => {
    const span = Math.max(1, endTime - startTime);
    const firstHour = Math.ceil(startTime / 3600) * 3600;
    const ticks = [];
    for (let t = firstHour; t <= endTime; t += 3600) {
      ticks.push({ t, pct: ((t - startTime) / span) * 100, label: secondsToHHMM(t) });
    }
    return ticks;
  }, [startTime, endTime]);

  return (
    <div className="aero-card px-4 pt-2 pb-1">
      <div className="flex items-center justify-between mb-1">
        <span className="panel-title">Event timeline</span>
        <div className="flex gap-3">
          {Object.entries(MARKER_STYLE).slice(0, 4).map(([k, v]) => (
            <span key={k} className="text-[9px] uppercase tracking-wider text-aero-muted">
              <span style={{ color: v.color }}>{v.symbol}</span> {v.label}
            </span>
          ))}
        </div>
      </div>

      <div className="relative h-9">
        {/* track */}
        <div className="absolute top-[13px] left-0 right-0 h-1.5 rounded-full bg-aero-bg border border-aero-border/60" />
        {/* progress fill */}
        <div
          className="absolute top-[13px] left-0 h-1.5 rounded-full bg-gradient-to-r from-aero-blue/40 to-aero-blue/80"
          style={{ width: `${progressPct}%` }}
        />
        {/* hour ticks */}
        {hourTicks.map((tick) => (
          <div key={tick.t} className="absolute top-[20px]" style={{ left: `${tick.pct}%` }}>
            <div className="w-px h-1.5 bg-aero-border mx-auto" />
            <div className="text-[8px] font-mono text-aero-muted -translate-x-1/2 mt-px">
              {tick.label}
            </div>
          </div>
        ))}
        {/* playhead */}
        <div
          className="absolute top-0 h-[22px] w-px bg-aero-blue shadow-glow"
          style={{ left: `${progressPct}%` }}
        >
          <div className="absolute -top-0.5 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-aero-blue" />
        </div>
        {/* event markers */}
        {markers.map((m) => {
          const style = MARKER_STYLE[m.event.event_type];
          if (!style) return null;
          return (
            <button
              key={m.event.index}
              onClick={() => onJump(m.event.index)}
              title={`${m.event.sim_time} — ${style.label}${m.event.flight_id ? ` (${m.event.flight_id})` : ""}`}
              className="absolute top-[8px] -translate-x-1/2 text-[11px] leading-none hover:scale-150 transition-transform z-10"
              style={{
                left: `${m.positionPct}%`,
                color: style.color,
                opacity: m.fired ? 1 : 0.3,
                filter: m.fired ? `drop-shadow(0 0 3px ${style.color})` : "none",
              }}
            >
              {style.symbol}
            </button>
          );
        })}
      </div>
      <div className="text-right text-[9px] font-mono text-aero-muted">
        ▶ {secondsToHHMM(simTime)}
      </div>
    </div>
  );
}
