"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type { ResearchReportOut, ResearchReportSummary, RunAccepted } from "@/lib/types";

interface UseReportsParams {
  ticker?: string;
  portfolio_id?: string;
  limit?: number;
  offset?: number;
}

export function useReports(params: UseReportsParams = {}) {
  const api = useApi();
  const [data, setData] = useState<ResearchReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      if (params.ticker) qs.set("ticker", params.ticker);
      if (params.portfolio_id) qs.set("portfolio_id", params.portfolio_id);
      if (params.limit != null) qs.set("limit", String(params.limit));
      if (params.offset != null) qs.set("offset", String(params.offset));
      const result = await api.get<ResearchReportSummary[]>(
        `/research/reports?${qs.toString()}`,
      );
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load reports");
    } finally {
      setLoading(false);
    }
  }, [api, params.ticker, params.portfolio_id, params.limit, params.offset]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useReport(id: string | null) {
  const api = useApi();
  const [data, setData] = useState<ResearchReportOut | null>(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<ResearchReportOut>(`/research/reports/${id}`);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load report");
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useStartResearchRun() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: {
      ticker: string;
      mode: "public" | "pre_ipo";
      lookback_days?: number;
      portfolio_id?: string;
    }): Promise<RunAccepted | null> => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<RunAccepted>("/research/runs", body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to start run");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  return { mutate, loading, error };
}
