"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/hooks/useApi";
import type { NotificationOut } from "@/lib/types";

/** `enabled` lets signed-out screens (like the sign-in page) skip polling instead of collecting 401s. */
export function useNotifications(unreadOnly = false, enabled = true) {
  const api = useApi();
  const [notifications, setNotifications] = useState<NotificationOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ limit: "50" });
      if (unreadOnly) qs.set("unread_only", "true");
      const result = await api.get<NotificationOut[]>(`/notifications?${qs.toString()}`);
      setNotifications(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, [api, unreadOnly]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    void fetch();
    timerRef.current = setInterval(() => void fetch(), 30_000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetch, enabled]);

  const markRead = useCallback(
    async (id: string) => {
      try {
        const updated = await api.post<NotificationOut>(`/notifications/${id}/read`);
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? updated : n)),
        );
      } catch {
        // ignore
      }
    },
    [api],
  );

  const unreadCount = notifications.filter((n) => n.read_at === null).length;

  return { notifications, unreadCount, markRead, loading, error, refetch: fetch };
}
