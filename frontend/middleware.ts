import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import { DEMO_COOKIE, DEMO_COOKIE_MAX_AGE_S } from "@/lib/demo";

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)"]);

export default clerkMiddleware(async (auth, request) => {
  // ?bypass-auth=true → set demo cookie and redirect without the param
  const url = new URL(request.url);
  if (url.searchParams.get("bypass-auth") === "true") {
    url.searchParams.delete("bypass-auth");
    // If no path remains, go straight to /research
    if (url.pathname === "/") url.pathname = "/research";
    const response = NextResponse.redirect(url);
    response.cookies.set(DEMO_COOKIE, "1", { path: "/", sameSite: "lax", maxAge: DEMO_COOKIE_MAX_AGE_S });
    return response;
  }

  // Demo cookie present → skip Clerk auth for all routes
  if (request.cookies.get(DEMO_COOKIE)?.value === "1") {
    return NextResponse.next();
  }

  if (!isPublicRoute(request)) {
    await auth.protect();
  }
}, {
  // Use the app's own sign-in/up pages (they carry the demo button) instead of Clerk's hosted portal.
  signInUrl: "/sign-in",
  signUpUrl: "/sign-up",
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
