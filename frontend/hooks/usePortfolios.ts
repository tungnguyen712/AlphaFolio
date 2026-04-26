"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type {
  AssetClass,
  HoldingOut,
  PendingPositionOut,
  PortfolioOut,
  PortfolioRecommendationOut,
  PortfolioWithHoldingsOut,
  RebalanceTriggerKind,
  RiskProfile,
  RunAccepted,
  TriggerOut,
} from "@/lib/types";

// ---- Portfolios ----

export function usePortfolios() {
  const api = useApi();
  const [data, setData] = useState<PortfolioOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<PortfolioOut[]>("/portfolios"));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load portfolios");
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function usePortfolio(id: string | null) {
  const api = useApi();
  const [data, setData] = useState<PortfolioWithHoldingsOut | null>(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<PortfolioWithHoldingsOut>(`/portfolios/${id}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useCreatePortfolio() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: { name: string; cash_balance: string; risk_profile: RiskProfile }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<PortfolioOut>("/portfolios", body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to create portfolio");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  return { mutate, loading, error };
}

export function useUpdatePortfolio(id: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: { name?: string; risk_profile?: RiskProfile; cash_balance?: string }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.patch<PortfolioOut>(`/portfolios/${id}`, body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to update portfolio");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, id],
  );

  return { mutate, loading, error };
}

export function useDeletePortfolio() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (id: string) => {
      setLoading(true);
      setError(null);
      try {
        await api.del(`/portfolios/${id}`);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to delete portfolio");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  return { mutate, loading, error };
}

// ---- Holdings ----

export function useAddHolding(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: { ticker: string; shares: string; avg_cost: string; asset_class: AssetClass }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<HoldingOut>(`/portfolios/${portfolioId}/holdings`, body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to add holding");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useUpdateHolding(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (
      holdingId: string,
      body: { shares?: string; avg_cost?: string; asset_class?: AssetClass },
    ) => {
      setLoading(true);
      setError(null);
      try {
        return await api.patch<HoldingOut>(
          `/portfolios/${portfolioId}/holdings/${holdingId}`,
          body,
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to update holding");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useDeleteHolding(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (holdingId: string) => {
      setLoading(true);
      setError(null);
      try {
        await api.del(`/portfolios/${portfolioId}/holdings/${holdingId}`);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to delete holding");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

// ---- Recommendations ----

export function usePortfolioRecommendations(portfolioId: string | null) {
  const api = useApi();
  const [data, setData] = useState<PortfolioRecommendationOut[]>([]);
  const [loading, setLoading] = useState(!!portfolioId);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await api.get<PortfolioRecommendationOut[]>(
          `/portfolios/${portfolioId}/recommendations?limit=20`,
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load recommendations");
    } finally {
      setLoading(false);
    }
  }, [api, portfolioId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

// ---- Pending positions ----

export function usePendingPositions(portfolioId: string | null) {
  const api = useApi();
  const [data, setData] = useState<PendingPositionOut[]>([]);
  const [loading, setLoading] = useState(!!portfolioId);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    try {
      setData(
        await api.get<PendingPositionOut[]>(`/portfolios/${portfolioId}/pending`),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load pending positions");
    } finally {
      setLoading(false);
    }
  }, [api, portfolioId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useCreatePendingPosition(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: { ticker: string; target_pct: string; source_report_id?: string }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<PendingPositionOut>(`/portfolios/${portfolioId}/pending`, body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to create pending position");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useAcceptPending(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (
      pendingId: string,
      body: { shares: string; avg_cost: string; asset_class: AssetClass },
    ) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<HoldingOut>(
          `/portfolios/${portfolioId}/pending/${pendingId}/accept`,
          body,
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to accept position");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useRejectPending(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (pendingId: string) => {
      setLoading(true);
      setError(null);
      try {
        await api.post(`/portfolios/${portfolioId}/pending/${pendingId}/reject`);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to reject position");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

// ---- Triggers ----

export function useTriggers(portfolioId: string | null) {
  const api = useApi();
  const [data, setData] = useState<TriggerOut[]>([]);
  const [loading, setLoading] = useState(!!portfolioId);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    try {
      setData(await api.get<TriggerOut[]>(`/portfolios/${portfolioId}/triggers`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load triggers");
    } finally {
      setLoading(false);
    }
  }, [api, portfolioId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useCreateTrigger(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: {
      kind: RebalanceTriggerKind;
      condition_json: Record<string, unknown>;
      fires_at?: string;
    }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<TriggerOut>(`/portfolios/${portfolioId}/triggers`, body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to create trigger");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useDeleteTrigger(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (triggerId: string) => {
      setLoading(true);
      setError(null);
      try {
        await api.del(`/portfolios/${portfolioId}/triggers/${triggerId}`);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to delete trigger");
        return false;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}

export function useStartPortfolioRun(portfolioId: string) {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: { candidate_report_ids?: string[]; objective?: string }) => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<RunAccepted>(`/portfolios/${portfolioId}/runs`, body);
      } catch (e) {
        setError(e instanceof Error ? e.message : "failed to start portfolio run");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api, portfolioId],
  );

  return { mutate, loading, error };
}
