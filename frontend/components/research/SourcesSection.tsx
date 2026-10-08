import type { SourceRef } from "@/lib/types";
import { noEmDash } from "@/lib/text";

function SourceList({
  title,
  idPrefix,
  label,
  items,
}: {
  title: string;
  idPrefix: string;
  label: string;
  items: SourceRef[];
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 font-serif text-lg font-semibold text-ink">{title}</h3>
      <ol className="space-y-2.5">
        {items.map((src, i) => (
          <li key={i} id={`${idPrefix}${i + 1}`} className="flex scroll-mt-40 gap-2 text-sm">
            <span className="mt-px w-7 shrink-0 text-muted">
              {label}
              {i + 1}
            </span>
            {src.url ? (
              <a href={src.url} target="_blank" rel="noopener noreferrer" className="leading-snug text-action">
                {noEmDash(src.label)}
              </a>
            ) : (
              <span className="leading-snug text-ink">{noEmDash(src.label)}</span>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Last block of the report. Numbers in the analysis ([1]) link to the news items here. */
export function SourcesSection({ sources }: { sources: SourceRef[] }) {
  if (!sources.length) return null;
  return (
    <section className="border-t-4 border-ink pt-5">
      <h2 className="mb-5 text-xl font-semibold">Sources</h2>
      <div className="grid gap-x-12 gap-y-8 md:grid-cols-2">
        <SourceList title="News" idPrefix="source-" label="" items={sources.filter((s) => s.kind === "news")} />
        <SourceList title="SEC filings" idPrefix="source-f" label="F" items={sources.filter((s) => s.kind === "sec_filing")} />
      </div>
    </section>
  );
}
