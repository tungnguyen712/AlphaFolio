"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useNotifications } from "@/hooks/useNotifications";
import { ThemeToggle } from "@/components/ui/ThemeToggle";
import { isDemoMode } from "@/lib/demo";
import type { NotificationOut } from "@/lib/types";

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

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { notifications, unreadCount, markRead } = useNotifications(false);
  const [bellOpen, setBellOpen] = useState(false);

  const [isDemo, setIsDemo] = useState(false);
  const [today, setToday] = useState("");
  useEffect(() => {
    setIsDemo(isDemoMode());
    setToday(
      new Date().toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" }),
    );
  }, []);

  const section = pathname.startsWith("/research")
    ? "The research desk"
    : pathname.startsWith("/portfolios")
      ? "The portfolio desk"
      : pathname.startsWith("/supply-chain")
        ? "The supply chain desk"
        : pathname.startsWith("/simulation")
          ? "The simulation desk"
          : "AlphaFolio";

  const tabClass = (prefix: string) =>
    `shrink-0 whitespace-nowrap border-b-[3px] pb-0.5 text-[1rem] transition-colors ${
      pathname.startsWith(prefix)
        ? "border-highlight font-semibold text-ink"
        : "border-transparent text-muted hover:text-ink"
    }`;

  const handleNotifClick = async (n: NotificationOut) => {
    setBellOpen(false);
    if (!n.read_at) await markRead(n.id);
    router.push(notifHref(n));
  };

  return (
    <header className="sticky top-0 z-30 bg-paper/95 backdrop-blur-sm">
      <div className="mx-auto w-full min-w-0 max-w-content px-4 sm:px-12">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 pt-5">
          <Link href="/" className="font-serif text-[1.5rem] font-semibold italic leading-none tracking-tight text-ink">
            AlphaFolio
          </Link>
          <nav
            aria-label="Main"
            className="no-scrollbar order-last flex w-full items-baseline gap-7 overflow-x-auto pb-1 sm:order-none sm:ml-auto sm:w-auto"
          >
            <Link href="/research" className={tabClass("/research")}>Research</Link>
            <Link href="/portfolios" className={tabClass("/portfolios")}>Portfolios</Link>
            <Link href="/supply-chain" className={tabClass("/supply-chain")}>Supply chain</Link>
            <Link href="/simulation" className={tabClass("/simulation")}>Simulation</Link>
            <Link href="/settings" className={tabClass("/settings")}>Settings</Link>
          </nav>

        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setBellOpen((v) => !v)}
              className="relative rounded p-1.5 text-muted hover:bg-rule/40 hover:text-ink"
              aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                />
              </svg>
              {unreadCount > 0 && (
                <span className="absolute right-0 top-0 flex h-4 w-4 items-center justify-center rounded-full bg-sell text-[11px] font-bold text-action-ink">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {bellOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-lg border border-rule bg-surface shadow-lg">
                <div className="border-b border-rule px-4 py-3">
                  <p className="text-sm font-semibold text-ink">Notifications</p>
                </div>
                <ul className="max-h-72 divide-y divide-rule overflow-y-auto">
                  {notifications.slice(0, 8).map((n) => (
                    <li key={n.id}>
                      <button
                        onClick={() => void handleNotifClick(n)}
                        className="w-full px-4 py-3 text-left hover:bg-rule/30"
                      >
                        <p
                          className={`text-sm ${n.read_at ? "text-muted" : "font-medium text-ink"}`}
                        >
                          {n.kind === "run_complete"
                            ? "Run completed"
                            : n.kind === "rebalance_trigger"
                              ? "Rebalance trigger fired"
                              : "Notification"}
                        </p>
                        <p className="mt-0.5 text-sm tabular-nums text-muted">
                          {new Date(n.created_at).toLocaleDateString()}
                        </p>
                      </button>
                    </li>
                  ))}
                  {notifications.length === 0 && (
                    <li className="px-4 py-6 text-sm text-muted">
                      Nothing new. Run or rebalance alerts will show up here.
                    </li>
                  )}
                </ul>
                <div className="border-t border-rule px-4 py-2">
                  <Link
                    href="/notifications"
                    onClick={() => setBellOpen(false)}
                    className="text-sm text-action hover:underline"
                  >
                    View all
                  </Link>
                </div>
              </div>
            )}
          </div>

          <ThemeToggle />
          {isDemo ? (
            <span className="rounded-sm bg-highlight px-2 py-0.5 text-sm font-semibold text-[#111]">Demo</span>
          ) : (
            <UserButton afterSignOutUrl="/sign-in" />
          )}
        </div>
        </div>

        <div className="mt-4 border-t-4 border-ink" />
        <div className="mt-1 border-t border-ink" />
        <div className="hidden justify-between py-2 text-sm text-muted sm:flex">
          <span suppressHydrationWarning>{today}</span>
          <span>{section}</span>
          <span>{isDemo ? "Demo edition" : ""}</span>
        </div>
        <div className="border-t border-ink" />
      </div>
    </header>
  );
}
