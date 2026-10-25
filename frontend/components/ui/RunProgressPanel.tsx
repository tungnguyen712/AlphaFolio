"use client";

import { useEffect } from "react";
import { useRun } from "@/hooks/useRuns";
import { useRunStream } from "@/hooks/useRunStream";
import { computeStages, friendlyRunError, stagesForFlow, type StageState } from "@/lib/runStages";
import type { AgentRunFlow, RunStatusOut } from "@/lib/types";
import { ButtonLink } from "./Button";
import { Spinner } from "./Spinner";

interface RunProgressPanelProps {
  runId: string;
  flow?: AgentRunFlow;
  onComplete?: (run: RunStatusOut) => void;
}

const dotClass: Record<StageState, string> = {
  done: "bg-buy",
  active: "bg-action motion-safe:animate-pulse",
  failed: "bg-sell",
  pending: "border-2 border-rule bg-paper",
};

const stateLabel: Record<StageState, string> = {
  done: "Completed",
  active: "In progress",
  failed: "Stopped",
  pending: "Up next",
};

export function RunProgressPanel({ runId, flow, onComplete }: RunProgressPanelProps) {
  const { steps, streamStatus, error: streamError, isStreaming } = useRunStream(runId);
  const { data: run } = useRun(runId);

  const isComplete = streamStatus === "complete" || run?.status === "complete";
  const isFailed =
    !!streamError ||
    streamStatus === "failed" ||
    streamStatus === "timeout" ||
    run?.status === "failed";

  useEffect(() => {
    if (streamStatus === "complete" && run && run.status === "complete") {
      onComplete?.(run);
    }
  }, [streamStatus, run, onComplete]);

  const stages = stagesForFlow(flow ?? run?.flow);
  const { views, completedCount } = computeStages(stages, steps, {
    isStreaming,
    failed: isFailed,
    complete: isComplete,
  });
  const total = views.length;
  const currentStep = Math.min(completedCount + 1, total);

  const heading = isFailed
    ? "We couldn't finish this report"
    : isComplete
      ? "Your report is ready"
      : run?.ticker
        ? `Researching ${run.ticker}`
        : "Getting started";

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        {!isFailed && !isComplete && <Spinner size="sm" />}
        <h2 className="text-xl font-semibold text-ink">{heading}</h2>
      </div>

      {isFailed ? (
        <div role="alert" className="mb-8 rounded-lg border border-sell/40 bg-sell-soft px-5 py-4">
          <p className="text-sm text-sell">{friendlyRunError(streamError ?? run?.error ?? null)}</p>
          <div className="mt-4">
            <ButtonLink href={flow === "portfolio" ? "/portfolios" : "/research"}>
              {flow === "portfolio" ? "Back to portfolios" : "Start a new research"}
            </ButtonLink>
          </div>
        </div>
      ) : (
        total > 1 && (
          <div className="mb-8">
            <p className="text-sm text-muted" aria-live="polite">
              {isComplete ? "All steps complete" : `Step ${currentStep} of ${total}`}
            </p>
            <div className="mt-2 h-1 w-full bg-rule" aria-hidden="true">
              <div
                className="h-full bg-action motion-safe:transition-[width] motion-safe:duration-500"
                style={{ width: `${(completedCount / total) * 100}%` }}
              />
            </div>
          </div>
        )
      )}

      {/* The stages are fixed and ordered, so a timeline is the right structure. */}
      <ol className="relative ml-1.5 border-l border-rule">
        {views.map(({ stage, state }) => (
          <li
            key={stage.key}
            className="relative pb-6 pl-6 last:pb-0"
            aria-current={state === "active" ? "step" : undefined}
          >
            <span
              className={`absolute -left-[6px] top-2 h-3 w-3 rounded-full ring-4 ring-paper ${dotClass[state]}`}
            />
            <p
              className={`text-base ${
                state === "pending" ? "text-muted" : state === "active" ? "font-semibold text-ink" : "font-medium text-ink"
              }`}
            >
              {stage.label}
              <span className="sr-only">{`: ${stateLabel[state]}`}</span>
            </p>
            {state === "active" && <p className="mt-0.5 text-sm text-muted">{stage.description}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
