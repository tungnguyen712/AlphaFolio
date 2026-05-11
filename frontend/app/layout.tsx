import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Nav } from "@/components/nav/Nav";

export const metadata: Metadata = {
  title: "AlphaFolio",
  description: "Multi-agent stock research and portfolio construction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <body className="min-h-screen bg-zinc-50 text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100">
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            <Nav />
            <main className="mx-auto w-full max-w-7xl min-w-0 px-6 py-8">{children}</main>
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
