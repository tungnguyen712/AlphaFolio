"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useNotifications } from "@/hooks/useNotifications";
import type { NotificationOut } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";

function notifHref(n: NotificationOut): string {
  const p = n.payload;
  if (n.kind === "run_complete") {
    const flow = p.flow as string | undefined;
    const runId = p.run_id as string | undefined;
    const pid = p.portfolio_id as string | undefined;
    if (flow === "research" && runId) return `/research/runs/${runId}/result`;
    if (pid) return `/portfolios/${pid}`;
  }
  if (n.kind === "rebalance_trigger") {
    const pid = p.portfolio_id as string | undefined;
    if (pid) return `/portfolios/${pid}/triggers`;
  }
  if (n.kind === "price_alert" || n.kind === "earnings_result" || n.kind === "watch_reminder") {
    const reportId = p.report_id as string | undefined;
    if (reportId) return `/research/reports/${reportId}`;
    const ticker = p.ticker as string | undefined;
    if (ticker) return `/research?ticker=${ticker}`;
  }
  return "/";
}

function notifLabel(kind: NotificationOut["kind"]): string {
  switch (kind) {
    case "run_complete": return "Run completed";
    case "rebalance_trigger": return "Rebalance trigger fired";
    case "price_alert": return "Price alert";
    case "earnings_result": return "Earnings result";
    case "watch_reminder": return "Watch reminder";
    default: return "Notification";
  }
}

export default function NotificationsPage() {
  const router = useRouter();
  const { notifications, markRead, loading, error } = useNotifications(false);
  const [readingId, setReadingId] = useState<string | null>(null);

  const handleClick = async (n: NotificationOut) => {
    if (readingId) return;
    if (!n.read_at) {
      setReadingId(n.id);
      await markRead(n.id);
    }
    router.push(notifHref(n));
  };

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div>
      <h2 className="mb-6 text-xl font-bold text-neutral-900 dark:text-zinc-100">Notifications</h2>
      {notifications.length === 0 ? (
        <EmptyState title="No notifications" description="You're all caught up." />
      ) : (
        <ul className="divide-y divide-neutral-100 rounded-xl border border-neutral-200 bg-white shadow-sm dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
          {notifications.map((n) => (
            <li key={n.id}>
              <button
                onClick={() => void handleClick(n)}
                disabled={readingId === n.id}
                className="flex w-full items-start justify-between px-6 py-4 text-left hover:bg-neutral-50 disabled:cursor-wait dark:hover:bg-zinc-800/60"
              >
                <div className="space-y-0.5">
                  <p
                    className={`text-sm ${n.read_at ? "text-neutral-500 dark:text-zinc-400" : "font-medium text-neutral-900 dark:text-zinc-100"}`}
                  >
                    {(n.payload.title as string | undefined) ?? notifLabel(n.kind)}
                  </p>
                  <p className="text-xs text-neutral-400 dark:text-zinc-500">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                  {!n.read_at && (
                    <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
                  )}
                </div>
                <span className="ml-4 text-xs text-neutral-400 dark:text-zinc-500">→</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
