"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type { AgentRunFlow, AgentRunStatus, RunStatusOut, RunStepOut } from "@/lib/types";

export function useRun(id: string | null) {
  const api = useApi();
  const [data, setData] = useState<RunStatusOut | null>(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const doFetch = useCallback(async () => {
    if (!id) return;
    try {
      const result = await api.get<RunStatusOut>(`/runs/${id}`);
      setData(result);
      setError(null);
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load run");
      return null;
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    if (!id) return;
    void doFetch();
  }, [id, doFetch]);

  // Poll while queued or running
  useEffect(() => {
    if (!data) return;
    if (data.status === "queued" || data.status === "running") {
      timerRef.current = setInterval(() => void doFetch(), 2000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [data?.status, doFetch]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error, refetch: doFetch };
}

export function useRuns(params: {
  flow?: AgentRunFlow;
  run_status?: AgentRunStatus;
  limit?: number;
  offset?: number;
} = {}) {
  const api = useApi();
  const [data, setData] = useState<RunStatusOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (params.flow) qs.set("flow", params.flow);
      if (params.run_status) qs.set("run_status", params.run_status);
      if (params.limit != null) qs.set("limit", String(params.limit));
      if (params.offset != null) qs.set("offset", String(params.offset));
      setData(await api.get<RunStatusOut[]>(`/runs?${qs.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [api, params.flow, params.run_status, params.limit, params.offset]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useRunSteps(id: string | null) {
  const api = useApi();
  const [data, setData] = useState<RunStepOut[]>([]);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api
      .get<RunStepOut[]>(`/runs/${id}/steps`)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "failed to load steps"),
      )
      .finally(() => setLoading(false));
  }, [api, id]);

  return { data, loading, error };
}
