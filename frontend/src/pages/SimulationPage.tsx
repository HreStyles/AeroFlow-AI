// Main AOCC dashboard: airport map + panels + playback controls.
// Everything renders from the precomputed event log — zero backend calls
// during playback (the only POST is the operator decision feedback).
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import PageLayout from "../components/layout/PageLayout";
import AirportMap from "../components/simulation/AirportMap";
import EventTimeline from "../components/simulation/EventTimeline";
import SimulationClock from "../components/simulation/SimulationClock";
import TimeControls from "../components/simulation/TimeControls";
import AIRecommendation from "../components/panels/AIRecommendation";
import BusinessImpact from "../components/panels/BusinessImpact";
import DisruptionAlert from "../components/panels/DisruptionAlert";
import LiveDataFeeds from "../components/panels/LiveDataFeeds";
import OperatorDecision from "../components/panels/OperatorDecision";
import OptionsTable from "../components/panels/OptionsTable";
import { useScenario } from "../hooks/useScenario";
import { useSimulation } from "../hooks/useSimulation";
import { useEventLog } from "../hooks/useEventLog";
import { api } from "../api/client";
import type { OperatorDecisionRecord } from "../types/recommendations";
import { secondsToTime } from "../utils/formatting";

export default function SimulationPage() {
  const { eventLog, airport } = useScenario();
  const sim = useSimulation(eventLog);
  const { markers, progressPct } = useEventLog(
    sim.events,
    sim.startTime,
    sim.endTime,
    sim.simTime
  );
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const [decisions, setDecisions] = useState<
    (OperatorDecisionRecord & { at: string })[]
  >([]);

  const handleDecide = useCallback(
    async (decision: OperatorDecisionRecord) => {
      if (!eventLog) return;
      await api.postDecision(eventLog.scenario_id, decision);
      setDecisions((prev) => [
        ...prev,
        { ...decision, at: secondsToTime(sim.simTime) },
      ]);
    },
    [eventLog, sim.simTime]
  );

  if (!eventLog || !airport) {
    return (
      <PageLayout>
        <div className="h-full flex flex-col items-center justify-center gap-3">
          <div className="text-aero-muted">No scenario loaded.</div>
          <div className="flex gap-3">
            <Link to="/presets" className="aero-btn-primary">
              Load a preset scenario
            </Link>
            <Link to="/build" className="aero-btn">
              Build a custom scenario
            </Link>
          </div>
        </div>
      </PageLayout>
    );
  }

  const isFallback = eventLog.prediction_source.startsWith("heuristic");

  return (
    <PageLayout
      fill
      navbarRight={
        <>
          <span className="text-xs text-aero-muted hidden lg:inline truncate max-w-[200px]">
            {eventLog.scenario_name}
          </span>
          <SimulationClock simTime={sim.simTime} />
          <TimeControls
            isPlaying={sim.isPlaying}
            speed={sim.speed}
            onTogglePlay={sim.togglePlay}
            onSetSpeed={sim.setSpeed}
            onStepForward={sim.stepForward}
            onReset={sim.reset}
          />
        </>
      }
    >
      <div className="h-full flex flex-col gap-2 p-2">
        {isFallback && (
          <div className="shrink-0 rounded border border-amber-500/40 bg-amber-500/10 text-aero-amber text-xs px-3 py-1.5">
            ⚠ Heuristic predictions — ML model not trained yet. Run{" "}
            <code className="font-mono">scripts/train_all.py</code> for real
            LightGBM predictions. Simulation and MILP optimization are real.
          </div>
        )}

        {/* main grid: alerts | map | recommendation */}
        <div className="flex-[3] grid grid-cols-[280px_1fr_300px] gap-2 min-h-0">
          <DisruptionAlert
            prediction={sim.activePrediction}
            cascade={sim.activeCascade}
          />
          <div className="aero-card p-1 min-h-0">
            <AirportMap
              airport={airport}
              flights={eventLog.flights}
              simTime={sim.simTime}
              flightDelays={sim.flightDelays}
              flightStatus={sim.flightStatus}
              activePrediction={sim.activePrediction}
              activeRecommendation={sim.activeRecommendation}
              activeCascade={sim.activeCascade}
              gdpActive={!!sim.activeGdp}
            />
          </div>
          <AIRecommendation
            recommendation={sim.activeRecommendation}
            cascade={sim.activeCascade}
            costModel={eventLog.cost_model}
          />
        </div>

        {/* second row: feeds | options table | decision */}
        <div className="flex-[2] grid grid-cols-[280px_1fr_300px] gap-2 min-h-0">
          <LiveDataFeeds
            airport={airport}
            flights={eventLog.flights}
            simTime={sim.simTime}
            activeGdp={sim.activeGdp}
            flightStatus={sim.flightStatus}
          />
          <OptionsTable
            recommendation={sim.activeRecommendation}
            selectedRank={selectedRank}
            onSelectRank={setSelectedRank}
          />
          <OperatorDecision
            recommendation={sim.activeRecommendation}
            selectedRank={selectedRank}
            decisions={decisions}
            onDecide={handleDecide}
          />
        </div>

        <div className="shrink-0">
          <EventTimeline
            markers={markers}
            progressPct={progressPct}
            startTime={sim.startTime}
            endTime={sim.endTime}
            simTime={sim.simTime}
            onJump={sim.jumpToEvent}
          />
        </div>
        <div className="shrink-0">
          <BusinessImpact
            firedEvents={sim.firedEvents}
            totalFlights={eventLog.flights.filter((f) => f.status !== "idle").length}
            validation={eventLog.validation}
          />
        </div>
      </div>
    </PageLayout>
  );
}
