"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { usePortfolio, useDeletePortfolio } from "@/hooks/usePortfolios";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-portfolio-title"
        className="w-full max-w-md rounded-lg border border-rule bg-surface p-6 shadow-xl"
      >
        <h2 id="delete-portfolio-title" className="text-xl font-semibold text-ink">
          Delete this portfolio?
        </h2>
        <p className="mt-2 text-base text-ink">
          <span className="font-semibold">{name}</span> and all of its holdings, recommendations, pending positions,
          and triggers will be permanently deleted. This can&apos;t be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel} disabled={loading}>
            Keep portfolio
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={loading}>
            {loading && <Spinner size="sm" />}
            Delete permanently
          </Button>
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

      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/portfolios" className="text-base text-muted hover:text-ink">
            ← Portfolios
          </Link>
          <h1 className="mt-1 text-3xl font-semibold text-ink">{portfolio?.name ?? "Portfolio"}</h1>
        </div>
        <Button variant="quiet" className="!px-0 text-sell hover:text-sell" onClick={() => setShowDeleteModal(true)}>
          Delete portfolio
        </Button>
      </div>

      <nav aria-label="Portfolio sections" className="no-scrollbar mb-10 flex gap-7 overflow-x-auto border-b border-ink">
        {tabs.map((tab) => {
          const href = `${base}${tab.suffix}`;
          const isActive =
            tab.suffix === "" ? pathname === base : pathname.startsWith(`${base}${tab.suffix}`);
          return (
            <Link
              key={tab.suffix}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={`-mb-px shrink-0 whitespace-nowrap border-b-[3px] py-3 text-base ${
                isActive ? "border-highlight font-semibold text-ink" : "border-transparent text-muted hover:text-ink"
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

