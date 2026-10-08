import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import { Fraunces, Instrument_Sans } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Nav } from "@/components/nav/Nav";

const sans = Instrument_Sans({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const serif = Fraunces({ subsets: ["latin"], style: ["normal", "italic"], variable: "--font-serif", display: "swap" });

export const metadata: Metadata = {
  title: "AlphaFolio",
  description: "Multi-agent stock research and portfolio construction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider signInUrl="/sign-in" signUpUrl="/sign-up">
      <html lang="en" suppressHydrationWarning className={`${sans.variable} ${serif.variable}`}>
        <body className="min-h-screen bg-paper font-sans text-base text-ink antialiased">
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
            <Nav />
            <main className="mx-auto w-full min-w-0 max-w-content px-4 pb-24 pt-8 sm:px-12">{children}</main>
          </ThemeProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
