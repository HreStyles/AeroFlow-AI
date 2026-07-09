import { secondsToTime } from "../../utils/formatting";

export default function SimulationClock({ simTime }: { simTime: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="aero-label">Sim time</span>
      <span className="font-mono text-lg font-bold text-aero-blue tabular-nums">
        {secondsToTime(simTime)}
      </span>
    </div>
  );
}
