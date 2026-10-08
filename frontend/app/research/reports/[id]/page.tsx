"use client";

import { useState } from "react";
import Link from "next/link";
import { useReport } from "@/hooks/useResearch";
import { AddToPortfolioModal } from "@/components/portfolio/AddToPortfolioModal";
import { ReportView } from "@/components/research/ReportView";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/Panel";

export default function ResearchReportPage({ params }: { params: { id: string } }) {
  const { data: report, loading, error, refetch } = useReport(params.id);
  const [modalOpen, setModalOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-muted">Loading report</span>
      </div>
    );
  }

  if (error) return <ErrorState title="Couldn't load this report" message={error} onRetry={refetch} />;
  if (!report) return null;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/research" className="text-base text-muted hover:text-ink">
            ← Research
          </Link>
          <span className="text-base text-muted">{new Date(report.created_at).toLocaleString()}</span>
        </div>
        {report.signal === "buy" && <Button onClick={() => setModalOpen(true)}>Add to portfolio</Button>}
      </div>

      <ReportView ticker={report.ticker} signal={report.signal} report={report.report} />

      <AddToPortfolioModal
        reportId={params.id}
        ticker={report.ticker}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
