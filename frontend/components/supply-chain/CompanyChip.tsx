import Link from "next/link";
import type { RelatedCompany } from "@/lib/types";

const confidenceDot: Record<string, string> = {
  high: "bg-green-500",
  medium: "bg-yellow-400",
  low: "bg-zinc-400",
};

const confidenceLabel: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

interface Props {
  company: RelatedCompany;
}

export function CompanyChip({ company }: Props) {
  const inner = (
    <div className="group relative flex items-center gap-2 rounded-lg border border-zinc-200 bg-white px-3 py-2 shadow-sm transition-colors hover:border-sky-300 hover:bg-sky-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-sky-700 dark:hover:bg-sky-950/30">
      <span
        className={`h-2 w-2 flex-shrink-0 rounded-full ${confidenceDot[company.confidence]}`}
        title={confidenceLabel[company.confidence]}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
          {company.name}
        </p>
        {company.ticker && (
          <p className="font-mono text-xs text-zinc-400 dark:text-zinc-500">
            {company.ticker}
          </p>
        )}
      </div>
      {company.research_url && (
        <span className="flex-shrink-0 text-xs font-medium text-sky-600 dark:text-sky-400">
          Research →
        </span>
      )}
      {company.evidence_snippet && (
        <div className="absolute bottom-full left-0 z-10 mb-1 hidden w-64 rounded-lg border border-zinc-200 bg-white p-2 text-xs text-zinc-600 shadow-lg group-hover:block dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
          &ldquo;{company.evidence_snippet}&rdquo;
        </div>
      )}
    </div>
  );

  if (company.research_url) {
    return (
      <Link href={company.research_url} className="block">
        {inner}
      </Link>
    );
  }
  return inner;
}
