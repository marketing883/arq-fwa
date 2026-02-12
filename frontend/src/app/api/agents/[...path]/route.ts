/**
 * Proxy for /api/agents/* requests to the FastAPI backend.
 *
 * Next.js rewrite proxies have a ~30 s default timeout that cannot be
 * configured.  Ollama LLM calls routinely take 30-60+ seconds, so
 * the rewrite proxy kills the connection before the backend responds.
 *
 * By handling these requests in an API route handler we bypass the
 * rewrite proxy entirely and can set our own 180 s timeout.
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.BACKEND_URL || "http://backend:8000";
const TIMEOUT_MS = 180_000; // 3 minutes

async function proxy(req: NextRequest, subpath: string) {
  const url = `${BACKEND}/api/agents/${subpath}`;

  const headers: Record<string, string> = {
    "content-type": req.headers.get("content-type") || "application/json",
  };

  const init: RequestInit & { signal: AbortSignal } = {
    method: req.method,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.text();
  }

  try {
    const resp = await fetch(url, init);
    const body = await resp.text();
    return new NextResponse(body, {
      status: resp.status,
      headers: {
        "content-type":
          resp.headers.get("content-type") || "application/json",
      },
    });
  } catch (err: unknown) {
    const message =
      err instanceof Error ? err.message : "Unknown proxy error";

    if (
      err instanceof DOMException ||
      (err instanceof Error && err.name === "TimeoutError")
    ) {
      return NextResponse.json(
        { detail: "Request timed out (180 s). The model may be overloaded." },
        { status: 504 },
      );
    }

    return NextResponse.json(
      { detail: `Backend proxy error: ${message}` },
      { status: 502 },
    );
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(req, params.path.join("/"));
}

export async function POST(
  req: NextRequest,
  { params }: { params: { path: string[] } },
) {
  return proxy(req, params.path.join("/"));
}
