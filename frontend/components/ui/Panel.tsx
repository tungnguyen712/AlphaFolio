import type { ReactNode } from "react";

/** Flat surface with a 1px rule. Use sparingly; prefer ruled lists inside a page. */
export function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return <section className={`rounded-sm border border-rule bg-surface ${className}`}>{children}</section>;
}

export function ErrorState({
  title = "Can't reach the server",
  message,
  onRetry,
}: {
  title?: string;
  message?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-sm border-l-4 border-sell bg-sell-soft px-5 py-4">
      <p className="font-medium text-sell">{title}</p>
      {message && <p className="mt-0.5 text-sm text-sell/90">{message}</p>}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded border border-sell/40 px-3 py-1 text-sm font-medium text-sell hover:bg-sell/10"
        >
          Try again
        </button>
      )}
    </div>
  );
}
