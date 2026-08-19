import { NextRequest, NextResponse } from "next/server";
import {
  ACCESS_COOKIE_NAME,
  isValidAccessCode,
} from "@/lib/access";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  let accessCode = "";
  try {
    const body = (await request.json()) as { accessCode?: unknown };
    if (typeof body.accessCode === "string") accessCode = body.accessCode.trim();
  } catch {
    return NextResponse.json({ detail: "잘못된 요청입니다." }, { status: 400 });
  }

  if (!(await isValidAccessCode(accessCode))) {
    return NextResponse.json(
      { detail: "접근 코드가 올바르지 않습니다." },
      { status: 401, headers: { "Cache-Control": "no-store" } }
    );
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set({
    name: ACCESS_COOKIE_NAME,
    value: accessCode,
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 180,
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
