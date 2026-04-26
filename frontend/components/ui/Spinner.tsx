const sizes = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-10 w-10" };

export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <div
      className={`${sizes[size]} animate-spin rounded-full border-2 border-neutral-200 border-t-neutral-600`}
      role="status"
      aria-label="loading"
    />
  );
}
