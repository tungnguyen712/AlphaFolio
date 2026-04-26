import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-zinc-50 px-8 py-16 text-center dark:border-zinc-700 dark:bg-zinc-900/50">
      {icon && <div className="mb-3 text-zinc-400 dark:text-zinc-500">{icon}</div>}
      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{title}</p>
      {description && (
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
