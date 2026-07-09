// Project overview + the A → B → C pipeline graphic.
import { Link } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";

const STAGES = [
  {
    id: "A",
    title: "Predict",
    tech: "LightGBM + SHAP",
    color: "#f59e0b",
    desc: "Delay probability and P10/P50/P90 duration distribution per flight, with confidence scoring and per-prediction factor attribution.",
  },
  {
    id: "B",
    title: "Simulate",
    tech: "Discrete-event engine",
    color: "#ef4444",
    desc: "Propagates predicted delays through the operational graph: aircraft rotations, gate occupancy, and passenger connections.",
  },
  {
    id: "C",
    title: "Optimize",
    tech: "MILP · OR-Tools",
    color: "#3b82f6",
    desc: "Searches gate reassignments, aircraft swaps, and rebooking combinations for the cost-minimizing feasible response, with provable optimality gap.",
  },
  {
    id: "H",
    title: "Human decides",
    tech: "Accept / override",
    color: "#22c55e",
    desc: "Operators review ranked options with full rationale. Every decision is logged — the feedback loop for retraining.",
  },
];

export default function LandingPage() {
  return (
    <PageLayout>
      <div className="max-w-5xl mx-auto p-6 space-y-10">
        <div className="text-center pt-10">
          <div className="text-5xl mb-4">✈</div>
          <h1 className="text-3xl font-bold tracking-tight">
            AeroFlow <span className="text-aero-blue">AI</span>
          </h1>
          <p className="text-aero-muted mt-2 max-w-2xl mx-auto leading-relaxed">
            An AI-powered Airport Operations Control Center decision support
            system. It predicts flight delays, simulates how they cascade
            through gates, rotations, and connections — then recommends the
            cost-optimal operational response, with a human in the loop.
          </p>
          <div className="flex justify-center gap-3 mt-6">
            <Link to="/presets" className="aero-btn-primary">
              Run a preset scenario
            </Link>
            <Link to="/build" className="aero-btn">
              Build your own
            </Link>
          </div>
        </div>

        {/* pipeline graphic */}
        <div>
          <h2 className="aero-label text-center mb-4">The decision pipeline</h2>
          <div className="grid md:grid-cols-4 gap-3">
            {STAGES.map((s, i) => (
              <div key={s.id} className="relative aero-card p-4">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center font-mono font-bold text-sm mb-2"
                  style={{ backgroundColor: `${s.color}22`, color: s.color }}
                >
                  {s.id}
                </div>
                <div className="font-semibold">{s.title}</div>
                <div className="font-mono text-[10px] mb-2" style={{ color: s.color }}>
                  {s.tech}
                </div>
                <p className="text-xs text-aero-muted leading-relaxed">{s.desc}</p>
                {i < STAGES.length - 1 && (
                  <div className="hidden md:block absolute top-1/2 -right-2.5 text-aero-muted z-10">
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid md:grid-cols-3 gap-3 pb-10">
          <div className="aero-card p-4">
            <div className="font-semibold text-sm mb-1">No hallucinated data</div>
            <p className="text-xs text-aero-muted leading-relaxed">
              Every value is tagged{" "}
              <span className="text-aero-green">provided</span>,{" "}
              <span className="text-aero-blue">derived</span>, or{" "}
              <span className="text-aero-amber">estimated</span> — required
              fields with no safe default are rejected, never guessed.
            </p>
          </div>
          <div className="aero-card p-4">
            <div className="font-semibold text-sm mb-1">Validated, not vibes</div>
            <p className="text-xs text-aero-muted leading-relaxed">
              MILP optimality gaps, 4-strategy baseline comparisons, and
              cost-weight sensitivity analysis ship with every scenario run.
            </p>
          </div>
          <div className="aero-card p-4">
            <div className="font-semibold text-sm mb-1">Event-log playback</div>
            <p className="text-xs text-aero-muted leading-relaxed">
              The pipeline emits a timestamped event log; the dashboard plays
              it back at 1–50x with step and jump-to-event — zero backend
              calls during playback.
            </p>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
