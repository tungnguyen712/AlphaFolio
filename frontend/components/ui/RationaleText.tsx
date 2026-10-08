import { ReportSections } from "@/components/research/ReportSections";
import { parseRationaleSections } from "@/lib/rationale";
import type { SourceRef } from "@/lib/types";

interface Props {
  text: string;
  sources: SourceRef[];
}

/**
 * Renders a stored rationale string (reports saved without `report_sections`).
 * Numbered ("1. Recommendation: ...") and "## Heading" formats become real headings;
 * anything else is shown as plain paragraphs with a bold lead.
 */
export function RationaleText({ text, sources }: Props) {
  const sections = parseRationaleSections(text) ?? { "": text };
  return <ReportSections sections={sections} sources={sources} />;
}
