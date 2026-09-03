"use client";

import { RotateCcw, TriangleAlert } from "lucide-react";

import "./globals.css";

export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="ko" className="dark">
      <body>
        <main className="flex min-h-dvh items-center justify-center bg-canvas px-5 py-10 text-ink">
          <section className="relative w-full max-w-xl overflow-hidden rounded-2xl border border-edge bg-surface p-7 shadow-2xl shadow-black/30 sm:p-10">
            <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-losses" />
            <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-losses/25 bg-losses/5 text-losses">
              <TriangleAlert size={20} aria-hidden />
            </span>
            <p className="mt-7 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-losses">
              System boundary
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink sm:text-3xl">
              앱을 시작하지 못했습니다.
            </h1>
            <p className="mt-3 text-sm leading-6 text-ink-secondary">
              핵심 화면을 구성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요. 저장된 투자 데이터는 이 동작으로 변경되지 않습니다.
            </p>
            {error.digest && (
              <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                Incident · {error.digest}
              </p>
            )}
            <button type="button" onClick={retry} className="btn-primary mt-7 inline-flex items-center gap-2">
              <RotateCcw size={16} aria-hidden />
              앱 다시 시작
            </button>
          </section>
        </main>
      </body>
    </html>
  );
}
