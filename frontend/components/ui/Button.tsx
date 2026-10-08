import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "quiet" | "danger";
type Size = "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-action text-action-ink hover:opacity-85",
  secondary: "border border-ink bg-transparent text-ink hover:bg-highlight hover:text-[#111]",
  quiet: "text-muted hover:bg-highlight/50 hover:text-ink",
  danger: "bg-sell text-action-ink hover:opacity-90",
};

const sizes: Record<Size, string> = {
  md: "h-9 px-4 text-sm font-semibold",
  lg: "h-12 px-6 text-base font-semibold",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md") {
  return `inline-flex items-center justify-center gap-2 rounded-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]}`;
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export function Button({ variant = "primary", size = "md", className = "", ...rest }: ButtonProps) {
  return <button {...rest} className={`${buttonClass(variant, size)} ${className}`} />;
}

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  children,
}: {
  href: string;
  variant?: Variant;
  size?: Size;
  children: ReactNode;
}) {
  return (
    <Link href={href} className={buttonClass(variant, size)}>
      {children}
    </Link>
  );
}
