"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";
import { ApiError } from "@/lib/api";
import type { RelatedCompany, SupplyChainReport } from "@/lib/types";

function normalizeSupplyChainReport(report: SupplyChainReport): SupplyChainReport {
  return {
    ...report,
    relationships: Array.isArray(report.relationships)
      ? report.relationships.filter((rel): rel is RelatedCompany => !!rel)
      : [],
    data_sources_used: Array.isArray(report.data_sources_used)
      ? report.data_sources_used
      : [],
    filing_url: report.filing_url ?? null,
    filed_at: report.filed_at ?? null,
    notes: report.notes ?? null,
  };
}

export function useSupplyChain(ticker: string | null) {
  const api = useApi();
  const [data, setData] = useState<SupplyChainReport | null>(null);
  const [loading, setLoading] = useState(!!ticker);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);

  const fetch = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const result = await api.get<SupplyChainReport>(
        `/supply-chain/${ticker.toUpperCase()}`,
      );
      setData(normalizeSupplyChainReport(result));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load supply chain data");
      }
    } finally {
      setLoading(false);
    }
  }, [api, ticker]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, notFound, refetch: fetch };
}
