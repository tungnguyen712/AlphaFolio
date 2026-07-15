"use client";

import { useAuth } from "@clerk/nextjs";
import { useMemo } from "react";
import { createApiClient } from "@/lib/api";
import { DEMO_TOKEN, isDemoMode } from "@/lib/demo";

export function useApi() {
  const { getToken } = useAuth();
  return useMemo(
    () =>
      createApiClient(
        isDemoMode() && DEMO_TOKEN
          ? () => Promise.resolve(DEMO_TOKEN)
          : () => getToken(),
      ),
    [getToken],
  );
}
