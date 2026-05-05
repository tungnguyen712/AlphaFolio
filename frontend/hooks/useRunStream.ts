"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { ApiError, streamRun } from "@/lib/api";
import type { RunStepOut } from "@/lib/types";

interface StreamStep extends Omit<RunStepOut, "id"> {
  id: string;
}

const BASE_RECONNECT_DELAY_MS = 500;
const MAX_RECONNECT_DELAY_MS = 15_000;

export function useRunStream(runId: string | null) {
  const { getToken } = useAuth();
  const [steps, setSteps] = useState<StreamStep[]>([]);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!runId) return;

    const controller = new AbortController();
    const latestEventIdRef = { current: null as string | null };
    const seenStepIds = new Set<string>();
    abortRef.current = controller;
    setIsStreaming(true);
    setSteps([]);
    setStreamStatus(null);
    setError(null);

    void (async () => {
      let attempts = 0;
      try {
        while (!controller.signal.aborted) {
          let receivedTerminalEvent = false;
          try {
            for await (const event of streamRun(
              runId,
              () => getToken(),
              controller.signal,
              latestEventIdRef.current,
            )) {
              if (controller.signal.aborted) break;
              attempts = 0;
              if (event.type === "step") {
                latestEventIdRef.current = event.id;
                // _error is an internal bookkeeping step; never shown to users.
                if (event.agent_name === "_error" || seenStepIds.has(event.id)) continue;
                seenStepIds.add(event.id);
                setSteps((prev) => [
                  ...prev,
                  {
                    id: event.id,
                    agent_name: event.agent_name,
                    output: event.output,
                    error: event.error,
                    llm_model: event.llm_model ?? null,
                    input_tokens: event.input_tokens ?? null,
                    output_tokens: event.output_tokens ?? null,
                    latency_ms: event.latency_ms ?? null,
                    estimated_cost_usd: event.estimated_cost_usd ?? null,
                    completed_at: event.completed_at,
                  },
                ]);
              } else if (event.type === "status") {
                setStreamStatus(event.status);
              } else if (event.type === "done") {
                receivedTerminalEvent = true;
                setStreamStatus(event.status);
                if (event.error) setError(event.error);
                break;
              }
            }
            if (receivedTerminalEvent || controller.signal.aborted) break;
          } catch (e) {
            if (controller.signal.aborted) break;
            if (e instanceof ApiError && e.status >= 400 && e.status < 500) {
              throw e;
            }
          }
          attempts += 1;
          await sleep(reconnectDelay(attempts), controller.signal);
        }
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e.message : "stream error");
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsStreaming(false);
        }
      }
    })();

    return () => {
      controller.abort();
      setIsStreaming(false);
    };
  }, [runId, getToken]);

  return { steps, streamStatus, error, isStreaming };
}

function reconnectDelay(attempts: number) {
  const exponential = BASE_RECONNECT_DELAY_MS * 2 ** Math.max(0, attempts - 1);
  return Math.min(MAX_RECONNECT_DELAY_MS, exponential);
}

function sleep(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve) => {
    const timeout = window.setTimeout(resolve, ms);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timeout);
        resolve();
      },
      { once: true },
    );
  });
}
