import { buttonClass } from "@/components/ui/Button";
import { DEMO_ENTRY_PATH } from "@/lib/demo";

/**
 * Entry to recruiter demo mode from the sign-in and sign-up pages.
 * This must be a plain <a>, not next/link: Link prefetches the URL, the middleware would set the
 * demo cookie on that prefetch, and demo mode would start without anyone clicking.
 */
export function DemoModeButton() {
  return (
    <div className="mt-6 w-full max-w-sm border-t border-ink pt-5 text-center">
      <a href={DEMO_ENTRY_PATH} className={`${buttonClass("secondary", "lg")} w-full`}>
        View the demo without signing in
      </a>
      <p className="mt-3 text-sm text-muted">Sample access for reviewers. To use your own data, sign in above.</p>
    </div>
  );
}
