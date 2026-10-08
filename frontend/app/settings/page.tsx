"use client";

import { useEffect, useState } from "react";
import { useGetToken } from "@/hooks/useGetToken";
import { getMe, getTelegramToken, patchMe } from "@/lib/api";
import type { UserOut } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/Panel";
import { PageHeader } from "@/components/ui/PageHeader";

export default function SettingsPage() {
  const gt = useGetToken();

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
      // Re-fetch when user returns to this tab after clicking START in Telegram
      const onFocus = async () => {
        window.removeEventListener("focus", onFocus);
        const updated = await getMe(gt).catch(() => null);
        if (updated) setUser(updated);
      };
      window.addEventListener("focus", onFocus);
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
    <div>
      <PageHeader title="Settings" />
      <div className="max-w-form">

      {error && (
        <div className="mb-6">
          <ErrorState title="Something went wrong" message={error} />
        </div>
      )}

      <section className="border-t border-rule pt-6">
        <h2 className="text-xl font-semibold text-ink">Telegram notifications</h2>
        <p className="mb-4 mt-1 text-base text-muted">
          Get price alerts and watch reminders in Telegram as well as in the app.
        </p>

        {user?.telegram_connected ? (
          <div className="flex flex-wrap items-center gap-4">
            <Chip tone="buy">
              Connected{user.telegram_chat_id ? `, chat ${user.telegram_chat_id}` : ""}
            </Chip>
            <Button variant="secondary" onClick={() => void handleDisconnect()} disabled={disconnecting}>
              {disconnecting ? "Disconnecting" : "Disconnect"}
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <ol className="list-decimal space-y-1 pl-5 text-base text-ink">
              <li>Select Connect Telegram to open the bot.</li>
              <li>Press Start in Telegram to link your account.</li>
              <li>Come back to this tab. The link expires after 10 minutes.</li>
            </ol>
            <Button onClick={() => void handleConnect()} disabled={linking}>
              {linking ? (
                "Generating link"
              ) : (
                <>
                  <TelegramIcon className="h-4 w-4" />
                  Connect Telegram
                </>
              )}
            </Button>
          </div>
        )}
      </section>
      </div>
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
