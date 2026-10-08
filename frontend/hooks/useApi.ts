"use client";

import { useMemo } from "react";
import { createApiClient } from "@/lib/api";
import { useGetToken } from "@/hooks/useGetToken";

export function useApi() {
  const getToken = useGetToken();
  return useMemo(() => createApiClient(getToken), [getToken]);
}
