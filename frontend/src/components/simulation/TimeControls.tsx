// Play/pause, speed multipliers, step-to-next-event, reset.
import { SPEEDS } from "../../hooks/useSimulation";

interface Props {
  isPlaying: boolean;
  speed: number;
  onTogglePlay: () => void;
  onSetSpeed: (s: number) => void;
  onStepForward: () => void;
  onReset: () => void;
}

export default function TimeControls({
  isPlaying,
  speed,
  onTogglePlay,
  onSetSpeed,
  onStepForward,
  onReset,
}: Props) {
  return (
    <div className="flex items-center gap-1.5">
      <button
        onClick={onReset}
        title="Reset to start"
        className="aero-btn px-2 font-mono"
      >
        ⏮
      </button>
      <button
        onClick={onTogglePlay}
        title={isPlaying ? "Pause" : "Play"}
        className="aero-btn-primary px-3 font-mono"
        data-testid="play-pause"
      >
        {isPlaying ? "⏸" : "▶"}
      </button>
      <button
        onClick={onStepForward}
        title="Step to next event"
        className="aero-btn px-2 font-mono"
      >
        ⏭
      </button>
      <div className="flex rounded overflow-hidden border border-aero-border ml-1">
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => onSetSpeed(s)}
            className={`px-2 py-1 text-xs font-mono transition-colors ${
              speed === s
                ? "bg-aero-blue text-white"
                : "text-aero-muted hover:text-aero-text"
            }`}
          >
            {s}x
          </button>
        ))}
      </div>
    </div>
  );
}
