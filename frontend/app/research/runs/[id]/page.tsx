"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { RunProgressPanel } from "@/components/ui/RunProgressPanel";
import { PageHeader } from "@/components/ui/PageHeader";
import type { RunStatusOut } from "@/lib/types";

export default function ResearchRunPage({ params }: { params: { id: string } }) {
  const router = useRouter();

  const handleComplete = useCallback(
    (_run: RunStatusOut) => {
      router.push(`/research/runs/${params.id}/result`);
    },
    [params.id, router],
  );

  return (
    <div>
      <PageHeader
        title="Research in progress"
        description="You'll be taken to the result as soon as the last agent finishes."
      />

      <div className="max-w-form">
        <RunProgressPanel runId={params.id} onComplete={handleComplete} />
      </div>
    </div>
  );
}
