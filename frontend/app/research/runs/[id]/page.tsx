"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { RunProgressPanel } from "@/components/ui/RunProgressPanel";
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
      <h2 className="mb-4 text-base font-semibold text-neutral-800 dark:text-zinc-100">Research in progress</h2>
      <RunProgressPanel runId={params.id} onComplete={handleComplete} />
    </div>
  );
}
