"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";
import { LockKeyhole } from "lucide-react";

const safeDestination = () => {
  if (typeof window === "undefined") return "/home";
  const candidate = new URLSearchParams(window.location.search).get("next");
  if (!candidate?.startsWith("/") || candidate.startsWith("//")) return "/home";
  try {
    const destination = new URL(candidate, window.location.origin);
    return destination.origin === window.location.origin
      ? `${destination.pathname}${destination.search}${destination.hash}`
      : "/home";
  } catch {
    return "/home";
  }
};

export default function LoginPage() {
  const [accessCode, setAccessCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!accessCode.trim() || submitting) return;
    setSubmitting(true);
    setError("");

    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accessCode: accessCode.trim() }),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as
          | { detail?: string }
          | null;
        setError(body?.detail || "로그인하지 못했습니다.");
        return;
      }
      window.location.replace(safeDestination());
    } catch {
      setError("네트워크 연결을 확인하고 다시 시도해주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-[100dvh] items-center justify-center px-5 py-10">
      <section className="w-full max-w-sm rounded-3xl border border-edge bg-surface p-6 shadow-2xl shadow-black/30 sm:p-8">
        <div className="mb-7 flex flex-col items-center text-center">
          <Image
            src="/icons/icon-192.png"
            alt=""
            width={72}
            height={72}
            priority
            className="mb-4 rounded-2xl shadow-lg shadow-primary-500/20"
          />
          <h1 className="text-2xl font-semibold text-ink">Insight Invest</h1>
          <p className="mt-2 text-sm leading-6 text-ink-muted">
            개인 투자 데이터 보호를 위해 접근 코드를 입력해주세요.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="access-code" className="input-label">
              Access Code
            </label>
            <div className="relative">
              <LockKeyhole
                aria-hidden
                size={18}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
              />
              <input
                id="access-code"
                type="password"
                autoComplete="current-password"
                autoCapitalize="none"
                spellCheck={false}
                value={accessCode}
                onChange={(event) => setAccessCode(event.target.value)}
                className="input pl-10"
                placeholder="접근 코드"
                required
                autoFocus
              />
            </div>
          </div>

          {error && (
            <p role="alert" className="text-sm text-losses">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={!accessCode.trim() || submitting}
            className="btn-primary w-full py-3"
          >
            {submitting ? "확인 중..." : "Open Dashboard"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs leading-5 text-ink-muted">
          로그인은 이 기기에 안전한 쿠키로 유지되며 접근 코드는 저장하지 않습니다.
        </p>
      </section>
    </main>
  );
}
