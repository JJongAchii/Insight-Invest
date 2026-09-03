"use client";

import Link from "next/link";
import { DatabaseZap, RotateCcw, TriangleAlert } from "lucide-react";

export default function ErrorBoundary({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <section className="relative my-2 overflow-hidden rounded-2xl border border-edge bg-surface px-6 py-10 sm:px-10 sm:py-14">
      <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-losses" />
      <div className="max-w-2xl">
        <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-losses/25 bg-losses/5 text-losses">
          <TriangleAlert size={20} aria-hidden />
        </span>
        <p className="mt-7 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-losses">
          Rendering interrupted
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink sm:text-3xl">
          화면을 완성하지 못했습니다.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-ink-secondary">
          일시적인 데이터 또는 렌더링 오류일 수 있습니다. 다시 시도해도 해결되지 않으면 데이터 상태에서 원천별 최신성을 확인해 주세요.
        </p>

        {error.digest && (
          <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
            Incident · {error.digest}
          </p>
        )}

        <div className="mt-7 flex flex-wrap gap-3">
          <button type="button" onClick={retry} className="btn-primary inline-flex items-center gap-2">
            <RotateCcw size={16} aria-hidden />
            다시 시도
          </button>
          <Link href="/data-trust" className="btn-secondary inline-flex items-center gap-2">
            <DatabaseZap size={16} aria-hidden />
            데이터 상태 보기
          </Link>
        </div>
      </div>
    </section>
  );
}
