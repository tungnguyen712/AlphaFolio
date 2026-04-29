"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Spinner } from "@/components/ui/Spinner";
import { useRunSimulation, useSimulations } from "@/hooks/useSimulation";
import Link from "next/link";
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
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">Simulation</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          Build a hypothetical portfolio and see how it would have performed vs any benchmark.
        </p>
      </div>

      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="space-y-6 rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        {/* Date range */}
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Start date
            </label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              max={endDate}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              End date
            </label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              min={startDate}
              max={today}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </div>
        </div>

        {/* Benchmark */}
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Benchmark ticker
          </label>
          <input
            type="text"
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value.toUpperCase())}
            placeholder="VOO"
            maxLength={16}
            className="w-32 rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-sm uppercase text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
          <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
            VOO = S&amp;P 500, QQQ = Nasdaq 100, or any ticker
          </p>
        </div>

        {/* Positions */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Portfolio positions
            </label>
            <span
              className={`text-xs font-mono ${weightOk ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}
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
                  className="w-28 rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-sm uppercase text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                />
                <input
                  type="number"
                  value={row.weight}
                  onChange={(e) => updateRow(i, "weight", e.target.value)}
                  placeholder="50"
                  min="0.1"
                  max="100"
                  step="0.1"
                  className="w-24 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                />
                <span className="text-xs text-zinc-400">%</span>
                {positions.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeRow(i)}
                    className="text-xs text-zinc-400 hover:text-red-500"
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
              className="mt-2 text-xs text-sky-600 hover:text-sky-700 dark:text-sky-400"
            >
              + Add ticker
            </button>
          )}
          {!weightOk && totalWeight > 0 && (
            <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
              Weights must sum to 100% (currently {totalWeight.toFixed(1)}%)
            </p>
          )}
        </div>

        {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading || !weightOk}
          className="flex items-center gap-2 rounded-lg bg-sky-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-40"
        >
          {loading && <Spinner size="sm" />}
          {loading ? "Running simulation…" : "Run simulation"}
        </button>
      </form>

      {/* Recent simulations */}
      {recent.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Recent simulations
          </h2>
          <ul className="space-y-2">
            {recent.map((sim) => (
              <li key={sim.id}>
                <Link
                  href={`/simulation/${sim.id}`}
                  className="flex items-center justify-between rounded-lg border border-zinc-200 bg-white px-4 py-3 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60"
                >
                  <div className="flex items-center gap-2 font-mono text-sm text-zinc-800 dark:text-zinc-100">
                    {sim.positions.map((p) => `${p.ticker} ${(p.weight * 100).toFixed(0)}%`).join(" · ")}
                  </div>
                  <span className="text-xs text-zinc-400 dark:text-zinc-500">
                    {sim.start_date} → {sim.end_date}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </main>
  );
}
