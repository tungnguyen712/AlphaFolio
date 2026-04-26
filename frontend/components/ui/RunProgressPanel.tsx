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

export function RunProgressPanel({ runId, onComplete }: RunProgressPanelProps) {
  const { steps, streamStatus, error: streamError, isStreaming } = useRunStream(runId);
  const { data: run } = useRun(runId);

  useEffect(() => {
    if (streamStatus === "complete" && run && run.status === "complete") {
      onComplete?.(run);
    }
  }, [streamStatus, run, onComplete]);

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center gap-3">
        {isStreaming && <Spinner size="sm" />}
        <h3 className="text-sm font-semibold text-neutral-700">
          {isStreaming
            ? "Running agents…"
            : streamStatus === "complete"
              ? "Run complete"
              : streamStatus === "failed" || streamStatus === "timeout"
                ? "Run failed"
                : "Waiting to start…"}
        </h3>
      </div>

      {streamError && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-semibold text-red-700">Something went wrong</p>
          <p className="mt-1 text-sm text-red-600">
            {streamError.startsWith("LookupError")
              ? "Could not find this ticker in market data sources. Check the symbol and try again."
              : streamError.startsWith("ValueError") || streamError.startsWith("KeyError")
                ? "Unexpected data format from a market data provider. Try again shortly."
                : "The analysis run failed. Our team has been notified. You can try running again."}
          </p>
        </div>
      )}

      <ol className="space-y-3">
        {steps.map((step) => (
          <li key={step.id} className="flex items-start gap-3">
            <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-neutral-400" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-neutral-800">{step.agent_name}</p>
              {step.error && (
                <p className="mt-0.5 text-xs text-red-600">{step.error}</p>
              )}
              {step.completed_at && (
                <p className="mt-0.5 text-xs text-neutral-400">
                  {new Date(step.completed_at).toLocaleTimeString()}
                </p>
              )}
            </div>
            <span className="shrink-0 text-xs text-neutral-400">
              {step.error ? "✗" : "✓"}
            </span>
          </li>
        ))}
      </ol>

      {steps.length === 0 && !isStreaming && !streamError && (
        <p className="text-sm text-neutral-500">No steps yet.</p>
      )}
    </div>
  );
}
