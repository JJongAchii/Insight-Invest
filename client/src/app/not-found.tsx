import Link from "next/link";
import { ArrowLeft, Compass, DatabaseZap } from "lucide-react";

import PageHeader from "@/components/ui/PageHeader";

export default function NotFound() {
  return (
    <div className="space-y-7 py-2">
      <PageHeader
        eyebrow="Unknown coordinate · 404"
        title="요청한 경로를 찾지 못했습니다."
        description="주소가 바뀌었거나 더 이상 제공되지 않는 화면입니다. 투자 판단 대시보드에서 다시 탐색해 주세요."
        meta={
          <>
            <span>ROUTE · UNRESOLVED</span>
            <span aria-hidden>·</span>
            <span>STATE · SAFE</span>
          </>
        }
      />

      <section className="relative overflow-hidden rounded-2xl border border-edge bg-surface px-6 py-10 sm:px-10 sm:py-14">
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-primary-400 via-primary-500 to-secondary-400"
        />
        <div className="max-w-2xl">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-full border border-primary-400/25 bg-primary-500/10 text-primary-300">
            <Compass size={20} aria-hidden />
          </span>
          <p className="mt-7 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">
            Navigation recovery
          </p>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            판단의 흐름이 끊기지 않도록 안전한 시작점으로 돌아가세요.
          </h2>
          <p className="mt-3 max-w-xl text-sm leading-6 text-ink-secondary">
            기존 데이터나 저장한 전략은 변경되지 않았습니다. 대시보드로 돌아가거나 데이터 상태를 먼저 확인할 수 있습니다.
          </p>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link href="/" className="btn-primary inline-flex items-center gap-2">
              <ArrowLeft size={16} aria-hidden />
              대시보드로 돌아가기
            </Link>
            <Link href="/data-trust" className="btn-secondary inline-flex items-center gap-2">
              <DatabaseZap size={16} aria-hidden />
              데이터 상태 보기
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
