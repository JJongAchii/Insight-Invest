import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  isValidAccessCode,
} from "@/lib/access";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const authenticated = await isValidAccessCode(
    request.cookies.get(ACCESS_COOKIE_NAME)?.value
  );
  const proxyReady = Boolean(
    (process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL) &&
      (process.env.API_KEY || process.env.NEXT_PUBLIC_API_KEY)
  );
  return NextResponse.json(
    { authenticated, proxyReady },
    { headers: { "Cache-Control": "no-store" } }
  );
}
