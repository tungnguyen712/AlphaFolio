"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { usePortfolio, useDeletePortfolio } from "@/hooks/usePortfolios";
import { Spinner } from "@/components/ui/Spinner";

const tabs = [
  { label: "Overview", suffix: "" },
  { label: "Holdings", suffix: "/holdings" },
  { label: "Runs", suffix: "/runs" },
  { label: "Recommendations", suffix: "/recommendations" },
  { label: "Pending", suffix: "/pending" },
  { label: "Triggers", suffix: "/triggers" },
];

function DeletePortfolioModal({
  name,
  onConfirm,
  onCancel,
  loading,
}: {
  name: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <h2 className="text-lg font-bold text-neutral-900">Delete portfolio?</h2>
        <p className="mt-2 text-sm text-neutral-600">
          You are about to permanently delete{" "}
          <span className="font-semibold text-neutral-900">{name}</span>. This will remove all
          holdings, recommendations, pending positions, and triggers. This action cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            onClick={onCancel}
            disabled={loading}
            className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {loading && <Spinner size="sm" />}
            Delete permanently
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PortfolioLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: { id: string };
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: portfolio } = usePortfolio(params.id);
  const { mutate: deletePortfolio, loading: deleting } = useDeletePortfolio();
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const base = `/portfolios/${params.id}`;

  const handleDelete = async () => {
    const ok = await deletePortfolio(params.id);
    if (ok) router.push("/portfolios");
  };

  return (
    <div>
      {showDeleteModal && portfolio && (
        <DeletePortfolioModal
          name={portfolio.name}
          onConfirm={() => void handleDelete()}
          onCancel={() => setShowDeleteModal(false)}
          loading={deleting}
        />
      )}

      <div className="mb-4 flex items-start justify-between">
        <div>
          <Link href="/portfolios" className="text-xs text-neutral-400 hover:text-neutral-600">
            ← All portfolios
          </Link>
          <h2 className="mt-1 text-xl font-bold text-neutral-900">
            {portfolio?.name ?? "Portfolio"}
          </h2>
        </div>
        <button
          onClick={() => setShowDeleteModal(true)}
          className="mt-1 rounded-md border border-red-200 px-3 py-1.5 text-xs font-medium text-red-500 hover:border-red-400 hover:bg-red-50 hover:text-red-700"
        >
          Delete portfolio
        </button>
      </div>

      <nav className="mb-6 flex gap-1 border-b border-neutral-200">
        {tabs.map((tab) => {
          const href = `${base}${tab.suffix}`;
          const isActive =
            tab.suffix === ""
              ? pathname === base
              : pathname.startsWith(`${base}${tab.suffix}`);
          return (
            <Link
              key={tab.suffix}
              href={href}
              className={`px-4 py-2 text-sm transition-colors ${
                isActive
                  ? "border-b-2 border-neutral-900 font-semibold text-neutral-900"
                  : "text-neutral-500 hover:text-neutral-800"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      {children}
    </div>
  );
}

