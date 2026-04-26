interface Delta {
  value: string;
  positive: boolean;
}

interface StatCardProps {
  label: string;
  value: string;
  delta?: Delta;
  mono?: boolean;
  loading?: boolean;
}

export function StatCard({ label, value, delta, mono = true, loading = false }: StatCardProps) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        {label}
      </p>
      {loading ? (
        <div className="mt-2 h-7 w-28 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
      ) : (
        <p className={`mt-1 text-xl font-bold text-zinc-900 dark:text-zinc-100 ${mono ? "font-mono" : ""}`}>
          {value}
        </p>
      )}
      {delta && !loading && (
        <p
          className={`mt-1 text-xs font-medium font-mono ${
            delta.positive
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-red-600 dark:text-red-400"
          }`}
        >
          {delta.positive ? "▲" : "▼"} {delta.value}
        </p>
      )}
    </div>
  );
}
