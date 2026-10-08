"use client";

import { useEffect } from "react";
import { useRun } from "@/hooks/useRuns";
import { useRunStream } from "@/hooks/useRunStream";
import type { RunStatusOut } from "@/lib/types";
import { Spinner } from "./Spinner";

interface RunProgressPanelProps {
  runId: string;
  onComplete?: (run: RunStatusOut) => void;
}

type StepStatus = "running" | "done" | "failed" | "pending";

const dotClass: Record<StepStatus, string> = {
  running: "bg-action animate-pulse",
  done: "bg-buy",
  failed: "bg-sell",
  pending: "bg-rule",
};

function StepAccounting({
  step,
}: {
  step: {
    llm_model: string | null;
    input_tokens: number | null;
    output_tokens: number | null;
    latency_ms: number | null;
    estimated_cost_usd: number | null;
  };
}) {
  const parts = [
    step.llm_model,
    step.latency_ms !== null ? `${(step.latency_ms / 1000).toFixed(1)}s` : null,
    step.input_tokens !== null || step.output_tokens !== null
      ? `${step.input_tokens ?? 0} in / ${step.output_tokens ?? 0} out`
      : null,
    step.estimated_cost_usd !== null ? `$${step.estimated_cost_usd.toFixed(4)}` : null,
  ].filter(Boolean);

  if (parts.length === 0) return null;
  return <p className="mt-0.5 text-sm tabular-nums text-muted">{parts.join(" · ")}</p>;
}

export function RunProgressPanel({ runId, onComplete }: RunProgressPanelProps) {
  const { steps, streamStatus, error: streamError, isStreaming } = useRunStream(runId);
  const { data: run } = useRun(runId);

  useEffect(() => {
    if (streamStatus === "complete" && run && run.status === "complete") {
      onComplete?.(run);
    }
  }, [streamStatus, run, onComplete]);

  const headerLabel = isStreaming
    ? "Running agents"
    : streamStatus === "complete"
      ? "Run complete"
      : streamStatus === "failed" || streamStatus === "timeout"
        ? "Run failed"
        : "Waiting to start";

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        {isStreaming && <Spinner size="sm" />}
        <h2 className="text-xl font-semibold text-ink">{headerLabel}</h2>
      </div>

      {streamError && (
        <div role="alert" className="mb-6 rounded-lg border border-sell/40 bg-sell-soft px-5 py-4">
          <p className="font-medium text-sell">Run failed</p>
          <p className="mt-0.5 text-sm text-sell/90">
            {streamError.startsWith("LookupError")
              ? "Could not find this ticker in market data sources. Check the symbol and try again."
              : streamError.startsWith("ValueError") || streamError.startsWith("KeyError")
                ? "Unexpected data format from a market data provider. Try again shortly."
                : "The analysis run failed. Start a new run to try again."}
          </p>
        </div>
      )}

      {/* The agents run in order, so a timeline is the right structure here. */}
      <ol className="relative ml-1.5 border-l border-rule">
        {steps.map((step, idx) => {
          const isLast = idx === steps.length - 1;
          const status: StepStatus = step.error
            ? "failed"
            : step.completed_at
              ? "done"
              : isStreaming && isLast
                ? "running"
                : "pending";
          return (
            <li key={step.id} className="relative pb-6 pl-6 last:pb-0">
              <span
                className={`absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full ring-4 ring-paper ${dotClass[status]}`}
              />
              <div className="flex items-baseline justify-between gap-4">
                <p className="text-base font-medium text-ink">{step.agent_name.replace(/_/g, " ")}</p>
                {step.completed_at && (
                  <span className="text-sm tabular-nums text-muted">
                    {new Date(step.completed_at).toLocaleTimeString()}
                  </span>
                )}
              </div>
              {step.error && <p className="mt-0.5 text-sm text-sell">{step.error}</p>}
              <StepAccounting step={step} />
            </li>
          );
        })}
      </ol>

      {steps.length === 0 && !isStreaming && !streamError && (
        <p className="text-base text-muted">No agents have started yet.</p>
      )}
    </div>
  );
}
