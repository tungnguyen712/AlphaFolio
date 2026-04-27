import type { SourceRef } from "@/lib/types";

/**
 * Extract 2-3 distinctive keywords from a source label that are likely
 * to appear verbatim in the rationale text.
 * Labels look like: "Forbes: Microsoft Plunges After Reporting Slowed Cloud Growth (2026-01-29)"
 */
function extractKeywords(label: string): string[] {
  // Strip date suffix "(2026-01-29)"
  const cleaned = label.replace(/\s*\(\d{4}-\d{2}-\d{2}\)\s*$/, "");

  // Outlet names to check first (appear in rationale as source attribution)
  const outlets = [
    "Forbes", "CNBC", "Bloomberg", "Reuters", "WSJ", "FT",
    "Benzinga", "TheStreet", "Barron", "Seeking Alpha",
    "BofA", "Goldman", "JPMorgan", "Morgan Stanley", "Stifel",
    "TipRanks", "Weiss",
  ];
  const found: string[] = [];
  for (const o of outlets) {
    if (cleaned.toLowerCase().includes(o.toLowerCase())) found.push(o);
  }

  // Extract quoted phrases or distinctive proper nouns from the headline
  // e.g. "Top Pick", "$18B Australia", "mid-teens", "growth-to-spending"
  const phrases = cleaned
    .split(/[:\u2014\-|]/)
    .slice(1) // everything after the outlet prefix
    .join(" ")
    .match(/\$[\d.]+[BMK]?\s*\w+|[\w\-]+\s+[\w\-]+/g) ?? [];

  for (const p of phrases.slice(0, 3)) {
    const trimmed = p.trim();
    if (trimmed.length >= 5 && !found.includes(trimmed)) {
      found.push(trimmed);
    }
  }

  return found.slice(0, 3);
}

function findCitations(sentence: string, news: SourceRef[]): number[] {
  const lower = sentence.toLowerCase();
  const cited: number[] = [];
  news.forEach((src, i) => {
    const keywords = extractKeywords(src.label);
    if (keywords.some((kw) => lower.includes(kw.toLowerCase()))) {
      cited.push(i + 1);
    }
  });
  return cited;
}

interface Props {
  text: string;
  sources: SourceRef[];
}

/**
 * Renders rationale with:
 * - Paragraph breaks on \n\n
 * - First sentence of each paragraph bold (topic sentence)
 * - Inline superscript citation markers [n] next to sentences whose content
 *   matches a news source label keyword
 */
export function RationaleText({ text, sources }: Props) {
  const news = sources.filter((s) => s.kind === "news");
  const paragraphs = text.split(/\n{2,}/).filter(Boolean);

  return (
    <div className="space-y-4">
      {paragraphs.map((para, pi) => {
        // Split paragraph into sentences on ". " boundaries, preserving punctuation
        const sentencePattern = /[^.!?]+[.!?]+["']?(?:\s|$)/g;
        const rawSentences = para.match(sentencePattern) ?? [para];

        return (
          <p key={pi} className="text-base leading-relaxed text-neutral-700 dark:text-zinc-300">
            {rawSentences.map((sentence, si) => {
              const isFirst = si === 0;
              const citations = news.length > 0 ? findCitations(sentence, news) : [];

              return (
                <span key={si}>
                  {isFirst ? (
                    <strong className="font-semibold text-neutral-900 dark:text-zinc-100">{sentence}</strong>
                  ) : (
                    sentence
                  )}
                  {citations.map((n) => (
                    <sup
                      key={n}
                      className="ml-0.5 text-[10px] font-semibold text-blue-500 select-none"
                    >
                      [{n}]
                    </sup>
                  ))}
                </span>
              );
            })}
          </p>
        );
      })}
    </div>
  );
}
