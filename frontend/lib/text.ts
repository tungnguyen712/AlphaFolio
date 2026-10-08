/**
 * Product rule: no em dashes in text users read. The backend already prevents new ones
 * (backend/app/services/llm/style.py); this cleans text stored before that rule existed.
 */
export function noEmDash(text: string): string {
  if (!text.includes("—")) return text;
  const cleaned = text.replace(/\s*—\s*/g, ", ");
  const edge = text.trimStart().startsWith("—") || text.trimEnd().endsWith("—");
  return edge ? cleaned.replace(/^[,\s]+|[,\s]+$/g, "") : cleaned;
}
