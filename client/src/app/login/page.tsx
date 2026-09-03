"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";
import { Database, LockKeyhole, ShieldCheck } from "lucide-react";

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
        setError(body?.detail || "접근 코드를 확인하지 못했습니다.");
        return;
      }
      window.location.replace(safeDestination());
    } catch {
      setError("네트워크 연결을 확인하고 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden bg-canvas px-4 py-6 sm:px-6 sm:py-10">
      <div aria-hidden className="absolute left-[8%] top-[-18rem] h-[34rem] w-[34rem] rounded-full border border-primary-400/10" />
      <div aria-hidden className="absolute left-[8%] top-[-18rem] h-[28rem] w-[28rem] rounded-full border border-secondary-400/10" />
      <span aria-hidden className="absolute left-[calc(8%+16rem)] top-[7.7rem] h-2 w-2 rounded-full bg-primary-400 shadow-[0_0_18px_rgba(155,126,255,0.8)]" />

      <section className="relative grid w-full max-w-5xl overflow-hidden rounded-[1.75rem] border border-edge-strong bg-surface/95 shadow-[0_30px_100px_rgba(0,0,0,0.35)] backdrop-blur-xl lg:grid-cols-[1.15fr_0.85fr]">
        <div className="relative hidden min-h-[570px] flex-col justify-between overflow-hidden border-r border-edge p-10 lg:flex">
          <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-primary-400 via-primary-500 to-secondary-400" />
          <div>
            <div className="flex items-center gap-3">
              <Image
                src="/icons/icon-192.png"
                alt=""
                width={44}
                height={44}
                priority
                className="rounded-xl shadow-lg shadow-primary-500/20"
              />
              <div>
                <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.2em] text-primary-300">Private decision system</p>
                <p className="mt-0.5 text-sm font-semibold text-ink">INSIGHT / INVEST</p>
              </div>
            </div>

            <h2 className="mt-16 max-w-md text-4xl font-semibold leading-[1.08] tracking-[-0.045em] text-ink">
              시장의 소음보다
              <br />
              <span className="bg-gradient-to-r from-primary-300 to-secondary-400 bg-clip-text text-transparent">판단의 근거</span>를 남깁니다.
            </h2>
            <p className="mt-5 max-w-md text-sm leading-7 text-ink-secondary">
              포트폴리오, 시장 국면, 연구 기록을 한 흐름으로 연결한 개인 투자 워크스페이스입니다.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-edge bg-edge">
            <div className="bg-raised p-4">
              <Database size={16} className="text-primary-300" aria-hidden />
              <p className="mt-3 text-xs font-medium text-ink">출처와 기준일</p>
              <p className="mt-1 text-[11px] leading-5 text-ink-muted">모든 핵심 숫자의 관측 시점을 확인합니다.</p>
            </div>
            <div className="bg-raised p-4">
              <ShieldCheck size={16} className="text-secondary-400" aria-hidden />
              <p className="mt-3 text-xs font-medium text-ink">개인 접근 전용</p>
              <p className="mt-1 text-[11px] leading-5 text-ink-muted">접근 코드는 저장하지 않습니다.</p>
            </div>
          </div>
        </div>

        <div className="flex min-h-[540px] flex-col justify-center p-6 sm:p-10 lg:min-h-[570px]">
          <div className="mb-9 flex items-center gap-3 lg:hidden">
            <Image
              src="/icons/icon-192.png"
              alt=""
              width={42}
              height={42}
              priority
              className="rounded-xl shadow-lg shadow-primary-500/20"
            />
            <div>
              <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.2em] text-primary-300">Private decision system</p>
              <p className="mt-0.5 font-semibold text-ink">Insight Invest</p>
            </div>
          </div>

          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Secure access</p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink">워크스페이스 열기</h1>
            <p className="mt-2 text-sm leading-6 text-ink-muted">
              개인 투자 데이터 보호를 위해 접근 코드를 입력해 주세요.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" aria-busy={submitting}>
            <div>
              <label htmlFor="access-code" className="input-label">
                Access code
              </label>
              <div className="relative">
                <LockKeyhole
                  aria-hidden
                  size={18}
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted"
                />
                <input
                  id="access-code"
                  type="password"
                  autoComplete="current-password"
                  autoCapitalize="none"
                  spellCheck={false}
                  value={accessCode}
                  onChange={(event) => setAccessCode(event.target.value)}
                  className={`${error ? "input-error" : "input"} h-12 pl-11`}
                  placeholder="접근 코드"
                  required
                  autoFocus
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? "access-error" : "access-privacy"}
                />
              </div>
            </div>

            {error && (
              <p id="access-error" role="alert" className="rounded-xl border border-losses/25 bg-losses/5 px-3 py-2.5 text-sm text-losses">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={!accessCode.trim() || submitting}
              className="btn-primary w-full py-3"
            >
              {submitting ? "접근 확인 중…" : "Insight Invest 열기"}
            </button>
          </form>

          <p id="access-privacy" className="mt-5 flex items-start gap-2 text-xs leading-5 text-ink-muted">
            <ShieldCheck size={14} className="mt-0.5 shrink-0 text-primary-300" aria-hidden />
            로그인은 이 기기의 보안 쿠키로 유지되며 입력한 접근 코드는 저장하지 않습니다.
          </p>
        </div>
      </section>
    </main>
  );
}
