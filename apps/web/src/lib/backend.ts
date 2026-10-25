import { NextResponse } from "next/server";

export function getBackendConfig() {
  const baseUrl = process.env.DOWNLOAD_API_URL?.replace(/\/$/, "");
  const apiKey = process.env.DOWNLOAD_API_KEY;

  if (!baseUrl || !apiKey) {
    return null;
  }

  return { baseUrl, apiKey };
}

export function backendNotConfigured() {
  return NextResponse.json(
    {
      detail:
        "Download backend is not configured. Set DOWNLOAD_API_URL and DOWNLOAD_API_KEY on the server.",
    },
    { status: 503 },
  );
}

export async function backendFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const config = getBackendConfig();
  if (!config) {
    throw new Error("BACKEND_NOT_CONFIGURED");
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${config.apiKey}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  return fetch(`${config.baseUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function proxyJson(path: string, init?: RequestInit) {
  try {
    const res = await backendFetch(path, init);
    const text = await res.text();
    let data: unknown = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { detail: text };
      }
    }
    return NextResponse.json(data ?? {}, { status: res.status });
  } catch (error) {
    if (error instanceof Error && error.message === "BACKEND_NOT_CONFIGURED") {
      return backendNotConfigured();
    }
    return NextResponse.json(
      { detail: "Could not reach the download service." },
      { status: 502 },
    );
  }
}
