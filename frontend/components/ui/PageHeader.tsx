import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-10">
      <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold text-ink">{title}</h1>
          {description && <p className="mt-3 max-w-reading text-lg text-muted">{description}</p>}
        </div>
        {action}
      </div>
      <div className="mt-6 border-t-4 border-ink" />
    </header>
  );
}
