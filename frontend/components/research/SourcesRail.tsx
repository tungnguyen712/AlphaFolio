import type { SourceRef } from "@/lib/types";
import { noEmDash } from "@/lib/text";

function SourceList({ title, prefix, items }: { title: string; prefix: string; items: SourceRef[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="mb-2 font-serif text-lg font-semibold text-ink">{title}</h3>
      <ol className="space-y-2.5">
        {items.map((src, i) => (
          <li key={i} className="flex gap-2 text-sm">
            <span className="mt-px w-6 shrink-0 tabular-nums text-muted">
              {prefix}
              {i + 1}
            </span>
            {src.url ? (
              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className="leading-snug text-action hover:underline"
              >
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

/** Footnote-style source list shown beside the rationale. Numbering matches the [n] citations in the text. */
export function SourcesRail({ sources }: { sources: SourceRef[] }) {
  if (!sources.length) return null;
  return (
    <aside className="space-y-6 border-t border-rule pt-6 lg:sticky lg:top-24 lg:self-start lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
      <h2 className="text-xl font-semibold text-ink">Sources</h2>
      <SourceList title="News" prefix="" items={sources.filter((s) => s.kind === "news")} />
      <SourceList title="SEC filings" prefix="F" items={sources.filter((s) => s.kind === "sec_filing")} />
    </aside>
  );
}
