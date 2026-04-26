"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { streamRun } from "@/lib/api";
import type { RunStepOut } from "@/lib/types";

interface StreamStep extends Omit<RunStepOut, "id"> {
  id: string; // synthetic client-side id
}

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
    abortRef.current = controller;
    setIsStreaming(true);
    setSteps([]);
    setStreamStatus(null);
    setError(null);

    void (async () => {
      try {
        for await (const event of streamRun(runId, () => getToken(), controller.signal)) {
          if (controller.signal.aborted) break;
          if (event.type === "step") {
            // _error is an internal bookkeeping step — never shown to users
            if (event.agent_name === "_error") continue;
            setSteps((prev) => [
              ...prev,
              {
                id: crypto.randomUUID(),
                agent_name: event.agent_name,
                output: event.output,
                error: event.error,
                completed_at: event.completed_at,
              },
            ]);
          } else if (event.type === "status") {
            setStreamStatus(event.status);
          } else if (event.type === "done") {
            setStreamStatus(event.status);
            if (event.error) setError(event.error);
            break;
          }
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
