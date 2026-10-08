import Link from "next/link";
import type { RelatedCompany } from "@/lib/types";

const confidenceLabel: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
};

/** Confidence is encoded by shape (filled / half / outline), so it doesn't rely on color alone. */
export function ConfidenceDot({ level }: { level: string }) {
  const style =
    level === "high"
      ? { background: "currentColor" }
      : level === "medium"
        ? { background: "linear-gradient(90deg, currentColor 50%, transparent 50%)" }
        : { background: "transparent" };
  return (
    <span
      role="img"
      aria-label={confidenceLabel[level] ?? level}
      title={confidenceLabel[level] ?? level}
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full border border-current text-ink"
      style={style}
    />
  );
}

interface Props {
  company: RelatedCompany;
}

export function CompanyChip({ company }: Props) {
  return (
    <div className="py-3">
      <div className="flex items-center gap-3">
        <ConfidenceDot level={company.confidence} />
        <p className="min-w-0 flex-1 truncate text-base font-medium text-ink">{company.name}</p>
        {company.ticker && <span className="text-sm font-medium text-muted">{company.ticker}</span>}
        {company.research_url && (
          <Link href={company.research_url} className="shrink-0 text-sm font-medium text-action hover:underline">
            Research {company.ticker ?? ""}
          </Link>
        )}
      </div>
      {company.evidence_snippet && (
        <p title={company.evidence_snippet} className="mt-1 line-clamp-2 pl-[1.375rem] text-sm text-muted">
          &ldquo;{company.evidence_snippet}&rdquo;
        </p>
      )}
    </div>
  );
}
