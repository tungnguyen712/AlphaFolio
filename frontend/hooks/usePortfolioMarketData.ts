"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type { PortfolioPricesOut } from "@/lib/types";

const _cache = new Map<string, { data: PortfolioPricesOut; ts: number }>();
const TTL = 5 * 60 * 1000;

export function usePortfolioMarketData(portfolioId: string | null) {
  const api = useApi();

  const cached = portfolioId ? _cache.get(portfolioId) : undefined;
  const cacheHit = !!cached && Date.now() - cached.ts < TTL;

  const [data, setData] = useState<PortfolioPricesOut | null>(cached?.data ?? null);
  const [loading, setLoading] = useState(!cacheHit && !!portfolioId);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!portfolioId) return;
    if (!cacheHit) setLoading(true);
    setError(null);
    try {
      const result = await api.get<PortfolioPricesOut>(`/portfolios/${portfolioId}/prices`);
      _cache.set(portfolioId, { data: result, ts: Date.now() });
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load market data");
    } finally {
      setLoading(false);
    }
  }, [api, portfolioId, cacheHit]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error };
}
