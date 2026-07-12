// Right-bottom: operator accept/override with reason capture — the
// human-in-the-loop accountability layer. Decisions POST to the backend
// feedback log.
import { useState } from "react";
import type { TimedEvent } from "../../hooks/useSimulation";
import type { OperatorDecisionRecord } from "../../types/recommendations";

interface Props {
  recommendation: TimedEvent | null;
  selectedRank: number | null;
  decisions: (OperatorDecisionRecord & { at: string })[];
  onDecide: (decision: OperatorDecisionRecord) => Promise<void>;
}

export default function OperatorDecision({
  recommendation,
  selectedRank,
  decisions,
  onDecide,
}: Props) {
  const [overriding, setOverriding] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const recId = recommendation?.details.recommendation_id as string | undefined;
  const decided = decisions.find((d) => d.recommendation_id === recId);
  const rank = selectedRank ?? 1;

  const submit = async (decision: "accepted" | "overridden") => {
    if (!recId) return;
    setSubmitting(true);
    try {
      await onDecide({
        recommendation_id: recId,
        selected_rank: decision === "accepted" ? 1 : rank,
        decision,
        override_reason: decision === "overridden" ? reason || "unspecified" : null,
      });
      setOverriding(false);
      setReason("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="aero-card h-full flex flex-col min-h-0">
      <div className="panel-header">
        <span className="panel-title">Operator decision</span>
        <span className="ml-auto text-[9px] font-mono text-aero-muted">human-in-the-loop</span>
      </div>
      <div className="p-3 flex-1 flex flex-col gap-2 min-h-0">
      {!recommendation ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-aero-muted text-xs">
          <span className="text-2xl opacity-40">☑</span>
          Awaiting recommendation
        </div>
      ) : decided ? (
        <div
          className={`rounded border p-2 text-xs ${
            decided.decision === "accepted"
              ? "border-green-500/30 bg-green-500/10"
              : "border-amber-500/30 bg-amber-500/10"
          }`}
        >
          <div className="font-medium">
            {decided.decision === "accepted" ? "✓ Accepted" : "⤳ Overridden"} — option #
            {decided.selected_rank}
          </div>
          {decided.override_reason && (
            <div className="text-aero-muted mt-1">Reason: {decided.override_reason}</div>
          )}
          <div className="text-[10px] text-aero-muted mt-1 font-mono">
            logged to feedback loop
          </div>
        </div>
      ) : overriding ? (
        <div className="space-y-2">
          <div className="text-xs">
            Override with option <span className="font-mono font-bold">#{rank}</span>{" "}
            <span className="text-aero-muted">(select a row in the options table)</span>
          </div>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Override reason (required for audit log)…"
            className="aero-input h-16 resize-none text-xs"
            data-testid="override-reason"
          />
          <div className="flex gap-2">
            <button
              onClick={() => submit("overridden")}
              disabled={submitting || !reason.trim()}
              className="aero-btn flex-1 border-aero-amber text-aero-amber hover:bg-amber-500/10"
            >
              Confirm override
            </button>
            <button onClick={() => setOverriding(false)} className="aero-btn">
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="text-xs text-aero-muted leading-snug">
            Review the recommendation and rationale, then accept or override.
            Every decision is logged for retraining.
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => submit("accepted")}
              disabled={submitting}
              className="aero-btn flex-1 border-aero-green text-aero-green hover:bg-green-500/10 font-medium"
              data-testid="accept-btn"
            >
              ✓ Accept #1
            </button>
            <button
              onClick={() => setOverriding(true)}
              disabled={submitting}
              className="aero-btn flex-1"
            >
              Override…
            </button>
          </div>
        </div>
      )}

      {decisions.length > 0 && (
        <div className="mt-auto pt-2 border-t border-aero-border min-h-0 overflow-y-auto">
          <div className="aero-label mb-1">Decision log</div>
          {decisions.map((d, i) => (
            <div key={i} className="text-[10px] font-mono text-aero-muted truncate">
              {d.at} · {d.recommendation_id} · {d.decision} #{d.selected_rank}
            </div>
          ))}
        </div>
      )}
      </div>
    </div>
  );
}
