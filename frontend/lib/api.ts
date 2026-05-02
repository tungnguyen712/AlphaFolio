import type { RunSseEvent, SupplyChainReport, TelegramTokenOut, UserOut } from "@/lib/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  getToken: () => Promise<string | null>,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore parse error, keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function createApiClient(getToken: () => Promise<string | null>) {
  return {
    get: <T>(path: string) => request<T>(path, getToken),
    post: <T>(path: string, body?: unknown) =>
      request<T>(path, getToken, {
        method: "POST",
        body: body !== undefined ? JSON.stringify(body) : undefined,
      }),
    patch: <T>(path: string, body: unknown) =>
      request<T>(path, getToken, { method: "PATCH", body: JSON.stringify(body) }),
    del: (path: string, body?: unknown) =>
      request<void>(path, getToken, {
        method: "DELETE",
        body: body !== undefined ? JSON.stringify(body) : undefined,
      }),
  };
}

export async function getSupplyChain(
  ticker: string,
  getToken: () => Promise<string | null>,
): Promise<SupplyChainReport> {
  const token = await getToken();
  const res = await fetch(`${BASE}/supply-chain/${ticker.toUpperCase()}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<SupplyChainReport>;
}

// SSE streaming via fetch — EventSource cannot set Authorization headers.
export async function* streamRun(
  runId: string,
  getToken: () => Promise<string | null>,
  signal?: AbortSignal,
): AsyncGenerator<RunSseEvent> {
  const token = await getToken();
  const res = await fetch(`${BASE}/runs/${runId}/stream`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    signal,
  });

  if (!res.ok || !res.body) {
    throw new ApiError(res.status, "stream unavailable");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      // SSE events are separated by double-newline
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const chunk of parts) {
        const dataLine = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!dataLine) continue;
        try {
          const event = JSON.parse(dataLine.slice(6)) as RunSseEvent;
          yield event;
          if (event.type === "done") return;
        } catch {
          // skip malformed event
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ---------------------------------------------------------------------------
// User / Settings
// ---------------------------------------------------------------------------

export async function getMe(
  getToken: () => Promise<string | null>,
): Promise<UserOut> {
  return request<UserOut>("/users/me", getToken);
}

export async function patchMe(
  updates: { telegram_chat_id: string | null },
  getToken: () => Promise<string | null>,
): Promise<UserOut> {
  return request<UserOut>("/users/me", getToken, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function getTelegramToken(
  getToken: () => Promise<string | null>,
): Promise<TelegramTokenOut> {
  return request<TelegramTokenOut>("/users/me/telegram-token", getToken);
}
