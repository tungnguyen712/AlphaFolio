import { CompanyChip } from "@/components/supply-chain/CompanyChip";
import type { RelatedCompany } from "@/lib/types";

interface Props {
  title: string;
  relationships: RelatedCompany[];
  emptyMessage: string;
}

export function RelationshipGroup({ title, relationships, emptyMessage }: Props) {
  return (
    <section>
      <h3 className="mb-1 flex items-baseline gap-2 border-b border-ink/30 pb-2 text-lg font-semibold text-ink">
        {title}
        <span className="text-sm font-normal text-muted">{relationships.length}</span>
      </h3>
      {relationships.length === 0 ? (
        <p className="py-3 text-base text-muted">{emptyMessage}</p>
      ) : (
        <div className="divide-y divide-rule">
          {relationships.map((rel, i) => (
            <CompanyChip key={`${rel.name}-${i}`} company={rel} />
          ))}
        </div>
      )}
    </section>
  );
}
