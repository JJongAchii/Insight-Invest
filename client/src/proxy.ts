import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  isValidAccessCode,
} from "@/lib/access";

const PUBLIC_PATHS = new Set([
  "/login",
  "/offline",
  "/manifest.webmanifest",
  "/sw.js",
  "/favicon.ico",
  "/api/auth/login",
  "/api/auth/status",
]);

const isPublicPath = (pathname: string) =>
  PUBLIC_PATHS.has(pathname) ||
  pathname.startsWith("/_next/") ||
  pathname.startsWith("/icons/");

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  if (isPublicPath(pathname)) return NextResponse.next();

  const accessCode = request.cookies.get(ACCESS_COOKIE_NAME)?.value;
  if (await isValidAccessCode(accessCode)) {
    const response = NextResponse.next();
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  }

  if (pathname.startsWith("/api/")) {
    return NextResponse.json(
      { detail: "로그인이 필요합니다." },
      { status: 401, headers: { "Cache-Control": "no-store" } }
    );
  }

  const loginUrl = new URL("/login", request.url);
  const destination = `${pathname}${search}`;
  if (destination !== "/") loginUrl.searchParams.set("next", destination);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!.*\\.).*)", "/sw.js", "/manifest.webmanifest"],
};
