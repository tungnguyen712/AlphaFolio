import type { ReactNode } from "react";
import { SENTENCE_RE, findCitations } from "@/lib/citations";
import { DISPLAY_SECTIONS } from "@/lib/rationale";
import type { SourceRef } from "@/lib/types";
import { noEmDash } from "@/lib/text";

type Block = { kind: "p"; text: string } | { kind: "ul"; items: string[] };

/** Split a section body into paragraphs and "- " bullet lists. */
function toBlocks(body: string): Block[] {
  const blocks: Block[] = [];
  for (const chunk of body.split(/\n{2,}/)) {
    let para: string[] = [];
    let list: string[] = [];
    const flushPara = () => {
      if (para.length) blocks.push({ kind: "p", text: para.join(" ") });
      para = [];
    };
    const flushList = () => {
      if (list.length) blocks.push({ kind: "ul", items: list });
      list = [];
    };
    for (const line of chunk.split("\n")) {
      const t = line.trim();
      if (!t) continue;
      if (t.startsWith("- ")) {
        flushPara();
        list.push(t.slice(2));
      } else {
        flushList();
        para.push(t);
      }
    }
    flushPara();
    flushList();
  }
  return blocks;
}

/** Reports written before bold leads existed: bold the first sentence so each section still has a lead. */
function withBoldLead(blocks: Block[], body: string): Block[] {
  if (body.includes("**")) return blocks;
  const i = blocks.findIndex((b) => b.kind === "p");
  if (i === -1) return blocks;
  const block = blocks[i];
  if (block.kind !== "p") return blocks;
  const first = block.text.match(SENTENCE_RE)?.[0];
  if (!first) return blocks;
  const next = blocks.slice();
  next[i] = { kind: "p", text: `**${first.trim()}**${block.text.slice(first.length)}` };
  return next;
}

/** Renders inline **bold** without showing the asterisks. */
function Inline({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-semibold text-ink">
            {p}
          </strong>
        ) : (
          p
        ),
      )}
    </>
  );
}

function Citations({ text, news }: { text: string; news: SourceRef[] }) {
  if (news.length === 0) return null;
  const cited = findCitations(text.replace(/\*\*/g, ""), news);
  return (
    <>
      {cited.map((n) => (
        <sup key={n} className="ml-0.5 text-[11px] font-semibold">
          <a href={`#source-${n}`} className="text-ink no-underline hover:underline" aria-label={`Source ${n}`}>
            [{n}]
          </a>
        </sup>
      ))}
    </>
  );
}

/**
 * The report's written analysis: one heading per section, a bold lead the reader can stop at,
 * then short paragraphs and bullet lists. Used by the saved report and the run result page.
 * An empty-string heading renders its body without a heading (plain prose reports).
 */
export function ReportSections({
  sections,
  sources,
}: {
  sections: Record<string, string>;
  sources: SourceRef[];
}): ReactNode {
  const news = sources.filter((s) => s.kind === "news");
  // Show only the reader-facing sections. Plain-prose reports (no known headings) are shown whole.
  const filtered = Object.keys(DISPLAY_SECTIONS).filter((h) => h in sections);
  const keys = filtered.length > 0 ? filtered : Object.keys(sections);
  const labelFor = (h: string) => (filtered.length > 0 ? DISPLAY_SECTIONS[h] : h);

  return (
    <div className="space-y-9">
      {keys.map((heading) => {
        const body = sections[heading] ?? "";
        const clean = noEmDash(body);
        const blocks = withBoldLead(toBlocks(clean), clean);
        return (
          <section key={heading || "body"}>
            {heading && <h3 className="mb-3 font-serif text-[1.35rem] font-semibold not-italic text-ink">{labelFor(heading)}</h3>}
            <div className="space-y-4">
              {blocks.map((b, i) =>
                b.kind === "p" ? (
                  <p key={i} className="text-[1.125rem] leading-[1.7] text-ink">
                    <Inline text={b.text} />
                    <Citations text={b.text} news={news} />
                  </p>
                ) : (
                  <ul key={i} className="list-disc space-y-2 pl-6 text-[1.125rem] leading-[1.6] text-ink marker:text-muted">
                    {b.items.map((item, j) => (
                      <li key={j}>
                        <Inline text={item} />
                        <Citations text={item} news={news} />
                      </li>
                    ))}
                  </ul>
                ),
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
