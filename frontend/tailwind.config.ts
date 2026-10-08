import type { Config } from "tailwindcss";

const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        paper: v("paper"),
        surface: v("surface"),
        ink: v("ink"),
        muted: v("muted"),
        rule: v("rule"),
        highlight: v("highlight"),
        action: v("action"),
        "action-ink": v("action-ink"),
        buy: v("buy"),
        hold: v("hold"),
        sell: v("sell"),
        "buy-soft": v("buy-soft"),
        "hold-soft": v("hold-soft"),
        "sell-soft": v("sell-soft"),
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Georgia", "serif"],
      },
      // Medium scale: ~30% below the first editorial draft. UI text stays 13-17px.
      fontSize: {
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.0625rem", { lineHeight: "1.6rem" }],
        xl: ["1.75rem", { lineHeight: "1.15" }],
        "2xl": ["2.5rem", { lineHeight: "1.08" }],
        "3xl": ["3.5rem", { lineHeight: "1.02", letterSpacing: "-0.03em" }],
        headline: ["clamp(3.25rem, 6.2vw, 6.65rem)", { lineHeight: "0.92", letterSpacing: "-0.04em" }],
        verdict: ["clamp(6rem, 9.4vw, 10rem)", { lineHeight: "0.85", letterSpacing: "-0.05em" }],
      },
      borderRadius: {
        DEFAULT: "2px",
        md: "2px",
        lg: "3px",
        xl: "4px",
      },
      maxWidth: {
        content: "85rem",
        reading: "44rem",
        form: "35rem",
      },
    },
  },
  plugins: [],
};

export default config;
