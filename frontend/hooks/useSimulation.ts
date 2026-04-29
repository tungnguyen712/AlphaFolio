"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/hooks/useApi";
import { ApiError } from "@/lib/api";
import type { SimPositionIn, SimRunOut } from "@/lib/types";

export function useSimulation(id: string | null) {
  const api = useApi();
  const [data, setData] = useState<SimRunOut | null>(null);
  const [loading, setLoading] = useState(!!id);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<SimRunOut>(`/simulation/runs/${id}`);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load simulation");
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useRunSimulation() {
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutate = useCallback(
    async (body: {
      positions: SimPositionIn[];
      start_date: string;
      end_date: string;
      benchmark: string;
    }): Promise<SimRunOut | null> => {
      setLoading(true);
      setError(null);
      try {
        return await api.post<SimRunOut>("/simulation/runs", body);
      } catch (e) {
        if (e instanceof ApiError) {
          setError(e.message);
        } else {
          setError(e instanceof Error ? e.message : "Failed to run simulation");
        }
        return null;
      } finally {
        setLoading(false);
      }
    },
    [api],
  );

  return { mutate, loading, error };
}

export function useSimulations() {
  const api = useApi();
  const [data, setData] = useState<SimRunOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get<SimRunOut[]>("/simulation/runs?limit=20")
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading };
}
