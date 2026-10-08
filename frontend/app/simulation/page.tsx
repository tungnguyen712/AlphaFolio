"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { useRunSimulation, useSimulations } from "@/hooks/useSimulation";
import Link from "next/link";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import type { SimPositionIn } from "@/lib/types";

interface PositionRow {
  ticker: string;
  weight: string;
}

const today = new Date().toISOString().slice(0, 10);
const oneYearAgo = new Date(Date.now() - 365 * 86400000).toISOString().slice(0, 10);

export default function SimulationPage() {
  const router = useRouter();
  const { mutate, loading, error } = useRunSimulation();
  const { data: recent } = useSimulations();

  const [positions, setPositions] = useState<PositionRow[]>([
    { ticker: "", weight: "" },
    { ticker: "", weight: "" },
  ]);
  const [benchmark, setBenchmark] = useState("VOO");
  const [startDate, setStartDate] = useState(oneYearAgo);
  const [endDate, setEndDate] = useState(today);

  const totalWeight = positions.reduce((s, p) => s + (parseFloat(p.weight) || 0), 0);
  const weightOk = Math.abs(totalWeight - 100) < 2;

  function addRow() {
    setPositions((prev) => [...prev, { ticker: "", weight: "" }]);
  }

  function removeRow(i: number) {
    setPositions((prev) => prev.filter((_, idx) => idx !== i));
  }

  function updateRow(i: number, field: "ticker" | "weight", value: string) {
    setPositions((prev) =>
      prev.map((row, idx) =>
        idx === i ? { ...row, [field]: field === "ticker" ? value.toUpperCase() : value } : row,
      ),
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const valid = positions
      .filter((p) => p.ticker.trim() && parseFloat(p.weight) > 0)
      .map<SimPositionIn>((p) => ({
        ticker: p.ticker.trim().toUpperCase(),
        weight: parseFloat(p.weight) / 100,
      }));
    if (valid.length === 0) return;

    const result = await mutate({
      positions: valid,
      start_date: startDate,
      end_date: endDate,
      benchmark: benchmark.toUpperCase(),
    });
    if (result) {
      router.push(`/simulation/${result.id}`);
    }
  }

  return (
    <div>
      <PageHeader
        title="Simulation"
        description="Build a hypothetical portfolio and see how it would have performed against a benchmark."
      />

      <div className="max-w-form">
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="space-y-6"
      >
        {/* Date range */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">
              Start date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate}
              className="w-full rounded border border-rule bg-surface px-3 py-2 text-sm text-ink focus:border-action focus:outline-none focus:ring-1 focus:ring-action"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">
              End date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate}
              max={today}
              className="w-full rounded border border-rule bg-surface px-3 py-2 text-sm text-ink focus:border-action focus:outline-none focus:ring-1 focus:ring-action"
            />
          </div>
        </div>

        {/* Benchmark */}
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">
            Benchmark ticker
          </label>
          <input
            type="text"
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value.toUpperCase())}
            placeholder="VOO"
            maxLength={16}
            className="w-32 rounded border border-rule bg-surface px-3 py-2 tabular-nums text-sm text-ink focus:border-action focus:outline-none focus:ring-1 focus:ring-action"
          />
          <p className="mt-1 text-sm text-muted">
            VOO = S&amp;P 500, QQQ = Nasdaq 100, or any ticker
          </p>
        </div>

        {/* Positions */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-sm font-medium text-ink">
              Portfolio positions
            </label>
            <span
              className={`text-sm tabular-nums ${weightOk ? "text-buy " : "text-hold "}`}
            >
              {totalWeight.toFixed(1)}% / 100%
            </span>
          </div>
          <div className="space-y-2">
            {positions.map((row, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="text"
                  value={row.ticker}
                  onChange={(e) => updateRow(i, "ticker", e.target.value)}
                  placeholder="AAPL"
                  maxLength={16}
                  className="w-28 rounded border border-rule bg-surface px-3 py-2 tabular-nums text-sm text-ink focus:border-action focus:outline-none focus:ring-1 focus:ring-action"
                />
                <input
                  type="number"
                  value={row.weight}
                  onChange={(e) => updateRow(i, "weight", e.target.value)}
                  placeholder="50"
                  min="0.1"
                  max="100"
                  step="0.1"
                  className="w-24 rounded border border-rule bg-surface px-3 py-2 text-sm text-ink focus:border-action focus:outline-none focus:ring-1 focus:ring-action"
                />
                <span className="text-sm text-muted">%</span>
                {positions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeRow(i)}
                    className="text-sm text-muted hover:text-sell"
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          {positions.length < 10 && (
            <button
              type="button"
              onClick={addRow}
              className="mt-2 text-base text-action hover:underline"
            >
              + Add ticker
            </button>
          )}
          {!weightOk && totalWeight > 0 && (
            <p className="mt-1 text-sm text-hold">
              Weights must sum to 100% (currently {totalWeight.toFixed(1)}%)
            </p>
          )}
        </div>

        {error && <p className="text-sm text-sell">{error}</p>}

        <Button type="submit" size="lg" disabled={loading || !weightOk}>
          {loading && <Spinner size="sm" />}
          {loading ? "Running simulation" : "Run simulation"}
        </Button>
      </form>

      {/* Recent simulations */}
      {recent.length > 0 && (
        <div className="mt-12">
          <h2 className="mb-3 text-xl font-semibold text-ink">
            Recent simulations
          </h2>
          <ul className="border-t border-rule">
            {recent.map((sim) => (
              <li key={sim.id}>
                <Link
                  href={`/simulation/${sim.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-1 py-3 hover:bg-rule/30"
                >
                  <div className="flex items-center gap-2 tabular-nums text-sm text-ink">
                    {sim.positions.map((p) => `${p.ticker} ${(p.weight * 100).toFixed(0)}%`).join(" · ")}
                  </div>
                  <span className="text-sm text-muted">
                    {sim.start_date} → {sim.end_date}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      </div>
    </div>
  );
}
