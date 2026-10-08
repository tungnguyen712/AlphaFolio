import type { ReactNode } from "react";

export const inputClass =
  "w-full rounded-sm border border-ink/40 bg-surface px-3 py-2 text-base text-ink placeholder:text-muted/70 focus:border-ink disabled:opacity-50";

interface FieldProps {
  label: string;
  hint?: string;
  error?: string | null;
  children: ReactNode;
}

/** Label + control + hint/error. Wraps the control in a <label> so clicking the text focuses it. */
export function Field({ label, hint, error, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-sm text-sell">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-sm text-muted">{hint}</span>
      ) : null}
    </label>
  );
}
