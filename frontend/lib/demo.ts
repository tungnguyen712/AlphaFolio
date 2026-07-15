/** Utilities for recruiter/demo bypass mode.
 *
 * Activated by visiting any page with ?bypass-auth=true.
 * The middleware sets the alphafolio_demo cookie and the token is read from
 * NEXT_PUBLIC_DEMO_BYPASS_TOKEN (must match DEMO_BYPASS_TOKEN on the backend).
 */

export const DEMO_TOKEN = process.env.NEXT_PUBLIC_DEMO_BYPASS_TOKEN ?? "";
export const DEMO_COOKIE = "alphafolio_demo";

/** Returns true when the user entered via ?bypass-auth=true (recruiter/demo mode).
 *  Safe to call in client components — returns false during SSR.
 */
export function isDemoMode(): boolean {
  if (typeof document === "undefined") return false;
  return document.cookie.split(";").some((c) => c.trim().startsWith(`${DEMO_COOKIE}=1`));
}
