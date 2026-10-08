import type { SourceRef } from "@/lib/types";

/** Sentence splitter that avoids breaking on decimal numbers like $347.81. */
export const SENTENCE_RE = /(?:[^.!?]|\.\d)+(?:[.!?]+["']?(?=\s|$))/g;

const OUTLETS = [
  "Forbes", "CNBC", "Bloomberg", "Reuters", "WSJ", "FT",
  "Benzinga", "TheStreet", "Barron", "Seeking Alpha",
  "BofA", "Goldman", "JPMorgan", "Morgan Stanley", "Stifel",
  "TipRanks", "Weiss",
];

/**
 * Extract 2-3 distinctive keywords from a source label that are likely
 * to appear verbatim in the rationale text.
 * Labels look like: "Forbes: Microsoft Plunges After Reporting Slowed Cloud Growth (2026-01-29)"
 */
function extractKeywords(label: string): string[] {
  // Strip date suffix "(2026-01-29)"
  const cleaned = label.replace(/\s*\(\d{4}-\d{2}-\d{2}\)\s*$/, "");

  const found: string[] = [];
  for (const o of OUTLETS) {
    if (cleaned.toLowerCase().includes(o.toLowerCase())) found.push(o);
  }

  // Distinctive phrases from the headline (everything after the outlet prefix)
  const phrases =
    cleaned
      .split(/[:—\-|]/)
      .slice(1)
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

/** 1-based indices of the news sources a piece of text appears to cite. */
export function findCitations(text: string, news: SourceRef[]): number[] {
  const lower = text.toLowerCase();
  const cited: number[] = [];
  news.forEach((src, i) => {
    const keywords = extractKeywords(src.label);
    if (keywords.some((kw) => lower.includes(kw.toLowerCase()))) {
      cited.push(i + 1);
    }
  });
  return cited;
}
