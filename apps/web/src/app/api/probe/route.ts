import { proxyJson } from "@/lib/backend";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  const body = await request.text();
  return proxyJson("/v1/probe", {
    method: "POST",
    body,
  });
}