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
  const phrases = cleaned
    .split(/[:—\-|]/)
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

/** Parse inline **bold** markers into React elements. */
function parseInlineBold(text: string): React.ReactNode[] {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className="font-semibold text-neutral-900 dark:text-zinc-100">
        {part}
      </strong>
    ) : (
      part
    )
  );
}

interface Props {
  text: string;
  sources: SourceRef[];
}

// Known section names in order — used to map old ## headings to numbers.
const KNOWN_SECTION_NAMES = [
  "Recommendation",
  "Investment Thesis",
  "Top Signals",
  "Valuation Bridge",
  "Key Uncertainties",
  "Devil's Advocate",
  "Data Quality",
  "Final Rationale",
];

/** Sentence splitter that avoids breaking on decimal numbers like $347.81. */
const SENTENCE_RE = /(?:[^.!?]|\.\d)+(?:[.!?]+["']?(?=\s|$))/g;

function renderSentences(text: string, news: SourceRef[]) {
  const sentences: string[] = text.match(SENTENCE_RE) ?? [text];
  return sentences.map((sentence, si) => {
    const citations = news.length > 0 ? findCitations(sentence, news) : [];
    return (
      <span key={si}>
        {parseInlineBold(sentence)}
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
  });
}

/**
 * Renders rationale for old-format reports (no report_sections).
 *
 * Handles:
 * - Paragraph breaks on \n{2+}
 * - New format: "1. Recommendation: content..." → numbered inline label
 * - Old format: "## Heading content..." → transformed to numbered inline label
 * - **bold** inline markdown
 * - First sentence of prose paragraphs bolded (topic sentence convention)
 * - Inline superscript citation markers [n]
 * - Decimal numbers (e.g. $347.81) are NOT split as sentence boundaries
 */
export function RationaleText({ text, sources }: Props) {
  const news = sources.filter((s) => s.kind === "news");
  const paragraphs = text.split(/\n{2,}/).filter(Boolean);

  return (
    <div className="space-y-4">
      {paragraphs.map((para, pi) => {
        // New numbered format: "1. Recommendation: HOLD — ..."
        const numberedMatch = para.match(/^(\d+)\.\s+([\w\s']+):\s*([\s\S]+)$/);
        if (numberedMatch) {
          const label = `${numberedMatch[1]}. ${numberedMatch[2]}:`;
          const body = numberedMatch[3];
          return (
            <p
              key={pi}
              className="text-base leading-relaxed text-neutral-700 dark:text-zinc-300"
            >
              <strong className="font-semibold text-neutral-900 dark:text-zinc-100">
                {label}{" "}
              </strong>
              {renderSentences(body, news)}
            </p>
          );
        }

        // Old ## heading format — transform to numbered inline if name is known
        const headingMatch = para.match(/^##\s+(.+)$/);
        if (headingMatch) {
          const fullText = headingMatch[1];
          let sectionNum: number | null = null;
          let sectionName: string | null = null;
          let bodyText = "";
          for (let ni = 0; ni < KNOWN_SECTION_NAMES.length; ni++) {
            if (fullText.startsWith(KNOWN_SECTION_NAMES[ni])) {
              sectionNum = ni + 1;
              sectionName = KNOWN_SECTION_NAMES[ni];
              bodyText = fullText.slice(KNOWN_SECTION_NAMES[ni].length).trim();
              break;
            }
          }
          if (sectionNum && sectionName && bodyText) {
            const label = `${sectionNum}. ${sectionName}:`;
            return (
              <p
                key={pi}
                className="text-base leading-relaxed text-neutral-700 dark:text-zinc-300"
              >
                <strong className="font-semibold text-neutral-900 dark:text-zinc-100">
                  {label}{" "}
                </strong>
                {renderSentences(bodyText, news)}
              </p>
            );
          }
          // Fallback: unknown heading → render as label only
          return (
            <h4
              key={pi}
              className="mt-2 text-sm font-semibold uppercase tracking-wider text-neutral-500 dark:text-zinc-400"
            >
              {fullText}
            </h4>
          );
        }

        // Plain prose paragraph — bold first sentence as topic sentence
        const rawSentences: string[] = para.match(SENTENCE_RE) ?? [para];
        return (
          <p
            key={pi}
            className="text-base leading-relaxed text-neutral-700 dark:text-zinc-300"
          >
            {rawSentences.map((sentence, si) => {
              const isFirst = si === 0;
              const citations = news.length > 0 ? findCitations(sentence, news) : [];
              const content = parseInlineBold(sentence);
              return (
                <span key={si}>
                  {isFirst ? (
                    <strong className="font-semibold text-neutral-900 dark:text-zinc-100">
                      {content}
                    </strong>
                  ) : (
                    content
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
