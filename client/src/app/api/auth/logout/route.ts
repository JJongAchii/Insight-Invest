import { NextResponse } from "next/server";
import { ACCESS_COOKIE_NAME } from "@/lib/access";

export async function POST() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set({
    name: ACCESS_COOKIE_NAME,
    value: "",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 0,
  });
  response.headers.set("Cache-Control", "no-store");
  return response;
}
