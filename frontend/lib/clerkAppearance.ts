/** Clerk needs concrete color values (not CSS variables), so these mirror the light-theme tokens in globals.css. */
export const clerkAppearance = {
  variables: {
    colorPrimary: "#111111",
    colorText: "#111111",
    colorTextSecondary: "#555555",
    colorBackground: "#FFFFFF",
    colorInputBackground: "#FFFFFF",
    fontFamily: "var(--font-sans), system-ui, sans-serif",
    borderRadius: "2px",
  },
  elements: {
    card: { boxShadow: "none", border: "1px solid #111111" },
    headerTitle: { fontFamily: "var(--font-serif), Georgia, serif", fontStyle: "italic" },
  },
};
