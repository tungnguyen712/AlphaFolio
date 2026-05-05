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

function StepDot({ status }: { status: "running" | "done" | "failed" | "pending" }) {
  if (status === "running") return <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sky-500 animate-pulse" />;
  if (status === "done") return <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />;
  if (status === "failed") return <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-red-500" />;
  return <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-zinc-300 dark:bg-zinc-600" />;
}

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
  return (
    <p className="mt-0.5 font-mono text-xs text-zinc-400 dark:text-zinc-500">
      {parts.join(" · ")}
    </p>
  );
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
    ? "Running agents…"
    : streamStatus === "complete"
      ? "Run complete"
      : streamStatus === "failed" || streamStatus === "timeout"
        ? "Run failed"
        : "Waiting to start…";

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-4 flex items-center gap-3">
        {isStreaming && <Spinner size="sm" />}
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">{headerLabel}</h3>
      </div>

      {streamError && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/40">
          <div className="flex items-start gap-2">
            <svg
              className="mt-0.5 h-4 w-4 shrink-0 text-red-500"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
            </svg>
            <div>
              <p className="text-sm font-semibold text-red-700 dark:text-red-300">Run failed</p>
              <p className="mt-0.5 text-sm text-red-600 dark:text-red-400">
                {streamError.startsWith("LookupError")
                  ? "Could not find this ticker in market data sources. Check the symbol and try again."
                  : streamError.startsWith("ValueError") || streamError.startsWith("KeyError")
                    ? "Unexpected data format from a market data provider. Try again shortly."
                    : "The analysis run failed. You can try running again."}
              </p>
            </div>
          </div>
        </div>
      )}

      <ol className="space-y-3">
        {steps.map((step, idx) => {
          const isLast = idx === steps.length - 1;
          const dotStatus = step.error ? "failed" : step.completed_at ? "done" : isStreaming && isLast ? "running" : "pending";
          return (
            <li key={step.id} className="flex items-start gap-3">
              <StepDot status={dotStatus} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200">{step.agent_name}</p>
                {step.error && (
                  <p className="mt-0.5 text-xs text-red-600 dark:text-red-400">{step.error}</p>
                )}
                {step.completed_at && (
                  <p className="mt-0.5 font-mono text-xs text-zinc-400 dark:text-zinc-500">
                    {new Date(step.completed_at).toLocaleTimeString()}
                  </p>
                )}
                <StepAccounting step={step} />
              </div>
              <span className={`shrink-0 text-xs font-mono ${step.error ? "text-red-500" : step.completed_at ? "text-emerald-500" : "text-zinc-400"}`}>
                {step.error ? "✗" : step.completed_at ? "✓" : "…"}
              </span>
            </li>
          );
        })}
      </ol>

      {steps.length === 0 && !isStreaming && !streamError && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">No steps yet.</p>
      )}
    </div>
  );
}
