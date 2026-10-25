import { NextResponse } from "next/server";
import { backendFetch, backendNotConfigured } from "@/lib/backend";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { id } = await context.params;

  try {
    const res = await backendFetch(`/v1/jobs/${encodeURIComponent(id)}/file`);
    if (!res.ok) {
      const text = await res.text();
      let detail = text;
      try {
        detail = JSON.parse(text).detail ?? text;
      } catch {
        /* keep text */
      }
      return NextResponse.json({ detail }, { status: res.status });
    }

    const headers = new Headers();
    const contentType = res.headers.get("content-type");
    const disposition = res.headers.get("content-disposition");
    if (contentType) headers.set("Content-Type", contentType);
    if (disposition) headers.set("Content-Disposition", disposition);
    headers.set("Cache-Control", "no-store");

    return new NextResponse(res.body, {
      status: 200,
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.message === "BACKEND_NOT_CONFIGURED") {
      return backendNotConfigured();
    }
    return NextResponse.json(
      { detail: "Could not download the file." },
      { status: 502 },
    );
  }
}