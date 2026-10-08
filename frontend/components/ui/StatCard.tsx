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

// `mono` is kept for call-site compatibility; figures use tabular numerals in the sans face.
export function StatCard({ label, value, delta, loading = false }: StatCardProps) {
  return (
    <div className="border-t-[3px] border-ink pt-3">
      <p className="text-sm text-muted">{label}</p>
      {loading ? (
        <div className="mt-2 h-8 w-28 animate-pulse rounded bg-rule/60" />
      ) : (
        <p className="mt-0.5 font-serif text-2xl font-semibold text-ink">{value}</p>
      )}
      {delta && !loading && (
        <p className={`mt-0.5 text-sm font-medium tabular-nums ${delta.positive ? "text-buy" : "text-sell"}`}>
          {delta.positive ? "▲" : "▼"} {delta.value}
        </p>
      )}
    </div>
  );
}
