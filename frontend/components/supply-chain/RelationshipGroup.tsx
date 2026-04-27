import { CompanyChip } from "@/components/supply-chain/CompanyChip";
import type { RelatedCompany } from "@/lib/types";

interface Props {
  title: string;
  relationships: RelatedCompany[];
  emptyMessage: string;
}

export function RelationshipGroup({ title, relationships, emptyMessage }: Props) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
        {title}
        <span className="ml-2 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
          {relationships.length}
        </span>
      </h3>
      {relationships.length === 0 ? (
        <p className="text-sm text-zinc-400 dark:text-zinc-500">{emptyMessage}</p>
      ) : (
        <div className="grid gap-2 sm:grid-cols-2">
          {relationships.map((rel, i) => (
            <CompanyChip key={`${rel.name}-${i}`} company={rel} />
          ))}
        </div>
      )}
    </div>
  );
}
