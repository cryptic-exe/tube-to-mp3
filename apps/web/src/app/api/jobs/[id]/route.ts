import { proxyJson } from "@/lib/backend";

export const runtime = "nodejs";
export const maxDuration = 30;

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;
  return proxyJson(`/v1/jobs/${encodeURIComponent(id)}`);
}