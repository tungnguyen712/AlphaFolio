"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useNotifications } from "@/hooks/useNotifications";
import type { NotificationOut } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/Panel";
import { PageHeader } from "@/components/ui/PageHeader";

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
  if (error) return <ErrorState title="Couldn't load notifications" message={error} />;

  return (
    <div>
      <PageHeader title="Notifications" description="Finished runs, price alerts, and rebalance triggers." />
      {notifications.length === 0 ? (
        <EmptyState title="Nothing new" description="When a run finishes or a rebalance trigger fires, it will show up here." />
      ) : (
        <ul className="max-w-3xl divide-y divide-rule border-y border-rule">
          {notifications.map((n) => (
            <li key={n.id}>
              <button
                onClick={() => void handleClick(n)}
                disabled={readingId === n.id}
                className="flex w-full items-start justify-between px-1 py-4 text-left hover:bg-rule/30 disabled:cursor-wait"
              >
                <div className="flex items-start gap-3">
                  <span
                    aria-label={n.read_at ? undefined : "Unread"}
                    className={`mt-2 h-2 w-2 shrink-0 rounded-full ${n.read_at ? "bg-transparent" : "bg-action"}`}
                  />
                  <div className="space-y-0.5">
                  <p
                    className={`text-base ${n.read_at ? "text-muted" : "font-semibold text-ink"}`}
                  >
                    {(n.payload.title as string | undefined) ?? notifLabel(n.kind)}
                  </p>
                  <p className="text-sm text-muted">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                  </div>
                </div>
                <span className="ml-4 text-sm text-muted">→</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
