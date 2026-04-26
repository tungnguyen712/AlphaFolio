"use client";

import { UserButton } from "@clerk/nextjs";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useNotifications } from "@/hooks/useNotifications";
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
  return "/";
}

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const { notifications, unreadCount, markRead } = useNotifications(false);
  const [bellOpen, setBellOpen] = useState(false);

  const isActive = (prefix: string) =>
    pathname.startsWith(prefix)
      ? "font-semibold text-neutral-900"
      : "text-neutral-500 hover:text-neutral-800";

  const handleNotifClick = async (n: NotificationOut) => {
    setBellOpen(false);
    if (!n.read_at) await markRead(n.id);
    router.push(notifHref(n));
  };

  return (
    <nav className="sticky top-0 z-30 border-b border-neutral-200 bg-white/90 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-base font-bold tracking-tight text-neutral-900">
            AlphaFolio
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/research" className={`text-sm font-medium transition-colors ${isActive("/research")}`}>
              Research
            </Link>
            <Link
              href="/portfolios"
              className={`text-sm font-medium transition-colors ${isActive("/portfolios")}`}
            >
              Portfolios
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Notification bell */}
          <div className="relative">
            <button
              onClick={() => setBellOpen((v) => !v)}
              className="relative rounded-md p-1.5 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-800"
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
                <span className="absolute right-0 top-0 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {bellOpen && (
              <div className="absolute right-0 mt-2 w-80 rounded-xl border border-neutral-200 bg-white shadow-lg">
                <div className="border-b border-neutral-100 px-4 py-3">
                  <p className="text-sm font-semibold text-neutral-800">Notifications</p>
                </div>
                <ul className="max-h-72 divide-y divide-neutral-100 overflow-y-auto">
                  {notifications.slice(0, 8).map((n) => (
                    <li key={n.id}>
                      <button
                        onClick={() => void handleNotifClick(n)}
                        className="w-full px-4 py-3 text-left hover:bg-neutral-50"
                      >
                        <p
                          className={`text-sm ${n.read_at ? "text-neutral-500" : "font-medium text-neutral-900"}`}
                        >
                          {n.kind === "run_complete"
                            ? "Run completed"
                            : n.kind === "rebalance_trigger"
                              ? "Rebalance trigger fired"
                              : "Notification"}
                        </p>
                        <p className="mt-0.5 text-xs text-neutral-400">
                          {new Date(n.created_at).toLocaleDateString()}
                        </p>
                      </button>
                    </li>
                  ))}
                  {notifications.length === 0 && (
                    <li className="px-4 py-6 text-center text-sm text-neutral-400">
                      No notifications
                    </li>
                  )}
                </ul>
                <div className="border-t border-neutral-100 px-4 py-2">
                  <Link
                    href="/notifications"
                    onClick={() => setBellOpen(false)}
                    className="text-xs text-neutral-500 hover:text-neutral-800"
                  >
                    View all
                  </Link>
                </div>
              </div>
            )}
          </div>

          <UserButton afterSignOutUrl="/sign-in" />
        </div>
      </div>
    </nav>
  );
}
