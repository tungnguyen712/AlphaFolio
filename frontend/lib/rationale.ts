/** Canonical section order (mirrors SECTION_HEADINGS in backend app/models/agents/synthesis.py). */
export const SECTION_ORDER = [
  "Recommendation",
  "Investment Thesis",
  "Top Signals",
  "Valuation Bridge",
  "Key Uncertainties",
  "Devil's Advocate",
  "Data Quality",
  "Final Rationale",
] as const;

/**
 * The sections shown to readers, with their display names. Reports saved before the analysis was cut
 * to three sections also hold Top Signals, Valuation Bridge, Key Uncertainties, Data Quality and Final
 * Rationale; those repeat other parts of the page (or are internal) and are not displayed.
 */
export const DISPLAY_SECTIONS: Record<string, string> = {
  Recommendation: "Recommendation",
  "Investment Thesis": "Investment thesis",
  "Devil's Advocate": "The case against",
};

/**
 * Split a stored rationale string into { heading: body }.
 * Handles the numbered format ("1. Recommendation: body") and the older "## Heading" format.
 * Returns null when the text has neither (plain prose).
 */
export function parseRationaleSections(text: string): Record<string, string> | null {
  const numbered = [...text.matchAll(/^(\d+)\.\s+([^:\n]+):\s*/gm)];
  if (numbered.length > 0) {
    const sections: Record<string, string> = {};
    numbered.forEach((m, i) => {
      const start = (m.index ?? 0) + m[0].length;
      const end = i + 1 < numbered.length ? (numbered[i + 1].index ?? text.length) : text.length;
      sections[m[2].trim()] = text.slice(start, end).trim();
    });
    return sections;
  }

  const legacy = [...text.matchAll(/^##\s+(.+)$/gm)];
  if (legacy.length > 0) {
    const sections: Record<string, string> = {};
    legacy.forEach((m, i) => {
      const line = m[1].trim();
      const start = (m.index ?? 0) + m[0].length;
      const end = i + 1 < legacy.length ? (legacy[i + 1].index ?? text.length) : text.length;
      const after = text.slice(start, end).trim();
      const known = SECTION_ORDER.find((name) => line.startsWith(name));
      if (known) {
        sections[known] = [line.slice(known.length).trim(), after].filter(Boolean).join("\n\n");
      } else {
        sections[line] = after;
      }
    });
    return sections;
  }

  return null;
}
