/** Utilities for recruiter/demo bypass mode.
 *
 * Activated by visiting any page with ?bypass-auth=true.
 * The middleware sets the alphafolio_demo cookie and the token is read from
 * NEXT_PUBLIC_DEMO_BYPASS_TOKEN (must match DEMO_BYPASS_TOKEN on the backend).
 */

export const DEMO_TOKEN = process.env.NEXT_PUBLIC_DEMO_BYPASS_TOKEN ?? "";
export const DEMO_COOKIE = "alphafolio_demo";

/** Demo mode lasts 8 hours, so it does not linger across days. */
export const DEMO_COOKIE_MAX_AGE_S = 60 * 60 * 8;

/** Where the "view the demo" button on the sign-in page sends people. Use a plain <a>, never next/link. */
export const DEMO_ENTRY_PATH = "/research?bypass-auth=true";

/** Returns true when the user entered via ?bypass-auth=true (recruiter/demo mode).
 *  Safe to call in client components — returns false during SSR.
 */
export function isDemoMode(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split(";").some((c) => c.trim().startsWith(`${DEMO_COOKIE}=1`));
}

/** Leaves demo mode by clearing the cookie. Call, then do a full navigation (not a client route change). */
export function exitDemoMode(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${DEMO_COOKIE}=; Max-Age=0; path=/; SameSite=Lax`;
}
