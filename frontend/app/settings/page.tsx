"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { getMe, getTelegramToken, patchMe } from "@/lib/api";
import type { UserOut } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";

export default function SettingsPage() {
  const { getToken } = useAuth();
  const gt = () => getToken();

  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  useEffect(() => {
    getMe(gt)
      .then(setUser)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleConnect = async () => {
    setLinking(true);
    setError(null);
    try {
      const tok = await getTelegramToken(gt);
      window.open(tok.deep_link, "_blank", "noopener,noreferrer");
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLinking(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("Disconnect Telegram? You will stop receiving push notifications.")) return;
    setDisconnecting(true);
    setError(null);
    try {
      const updated = await patchMe({ telegram_chat_id: null }, gt);
      setUser(updated);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setDisconnecting(false);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <h2 className="text-xl font-bold text-neutral-900 dark:text-zinc-100">Settings</h2>

      {error && (
        <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950/40 dark:text-red-400">
          {error}
        </p>
      )}

      {/* Telegram connection */}
      <section className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h3 className="mb-1 text-base font-semibold text-neutral-900 dark:text-zinc-100">
          Telegram Notifications
        </h3>
        <p className="mb-4 text-sm text-neutral-500 dark:text-zinc-400">
          Receive price alerts and watch reminders directly in Telegram.
        </p>

        {user?.telegram_connected ? (
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-sm font-medium text-green-700 dark:bg-green-950/40 dark:text-green-400">
              <span className="h-2 w-2 rounded-full bg-green-500" />
              Connected
              {user.telegram_chat_id && (
                <span className="ml-1 font-mono text-xs text-green-600 dark:text-green-500">
                  (chat {user.telegram_chat_id})
                </span>
              )}
            </span>
            <button
              onClick={() => void handleDisconnect()}
              disabled={disconnecting}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950/40"
            >
              {disconnecting ? "Disconnecting…" : "Disconnect"}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-neutral-600 dark:text-zinc-400">
              Click below to open Telegram and send the bot a message to link your account.
              The link expires in 10 minutes.
            </p>
            <button
              onClick={() => void handleConnect()}
              disabled={linking}
              className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
            >
              {linking ? (
                <>Generating link…</>
              ) : (
                <>
                  <TelegramIcon className="h-4 w-4" />
                  Connect Telegram
                </>
              )}
            </button>
          </div>
        )}
      </section>
    </div>
  );
}

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-2.026 9.551c-.15.668-.54.832-1.095.516l-3.023-2.228-1.46 1.404c-.162.162-.297.297-.607.297l.215-3.073 5.585-5.047c.242-.215-.054-.334-.375-.119L7.04 14.447l-2.98-.932c-.646-.203-.66-.646.135-.957l11.656-4.493c.539-.194 1.01.12.71.183z" />
    </svg>
  );
}
