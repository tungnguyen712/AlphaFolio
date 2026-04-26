import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav/Nav";

export const metadata: Metadata = {
  title: "AlphaFolio",
  description: "Multi-agent stock research and portfolio construction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
          <Nav />
          <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
        </body>
      </html>
    </ClerkProvider>
  );
}
