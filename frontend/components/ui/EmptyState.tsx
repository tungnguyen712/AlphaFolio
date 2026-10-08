import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="rounded-sm border border-dashed border-ink/40 px-6 py-12">
      {icon && <div className="mb-3 text-muted">{icon}</div>}
      <p className="font-serif text-xl italic text-ink">{title}</p>
      {description && <p className="mt-1 max-w-reading text-base text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
