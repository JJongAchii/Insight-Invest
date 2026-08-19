import { NextRequest, NextResponse } from "next/server";
import { ACCESS_COOKIE_NAME } from "@/lib/access";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type RouteContext = { params: Promise<{ path: string[] }> };

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

async function proxy(request: NextRequest, context: RouteContext) {
  const apiBaseUrl =
    process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL;
  const apiKey = process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY;
  const accessCode = request.cookies.get(ACCESS_COOKIE_NAME)?.value;

  if (!apiBaseUrl || !apiKey || !accessCode) {
    return NextResponse.json(
      { detail: "API 연결 설정을 확인할 수 없습니다." },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    );
  }

  const { path } = await context.params;
  const safePath = path.map(encodeURIComponent).join("/");
  const upstreamUrl = new URL(
    safePath,
    apiBaseUrl.endsWith("/") ? apiBaseUrl : `${apiBaseUrl}/`
  );
  upstreamUrl.search = request.nextUrl.search;

  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  const accept = request.headers.get("accept");
  if (contentType) headers.set("Content-Type", contentType);
  if (accept) headers.set("Accept", accept);
  headers.set("X-API-Key", apiKey);
  headers.set("X-Site-Access", accessCode);

  const hasBody = !["GET", "HEAD"].includes(request.method);
  try {
    const upstream = await fetch(upstreamUrl, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(115_000),
    });
    const responseHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP_HEADERS.has(key.toLowerCase())) {
        responseHeaders.set(key, value);
      }
    });
    responseHeaders.set("Cache-Control", "no-store");
    return new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { detail: "API 서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요." },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
