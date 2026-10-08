"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback } from "react";
import { DEMO_TOKEN, isDemoMode } from "@/lib/demo";

/**
 * Returns a stable `getToken` for API calls: the demo token in recruiter/demo mode, otherwise the Clerk session token.
 * Use this anywhere a hook or page needs a token outside `useApi` (e.g. the SSE run stream, Settings).
 */
export function useGetToken(): () => Promise<string | null> {
  const { getToken } = useAuth();
  return useCallback(
    () => (isDemoMode() && DEMO_TOKEN ? Promise.resolve(DEMO_TOKEN) : getToken()),
    [getToken],
  );
}
