import Image from "next/image";
import { DatabaseZap, RefreshCw, WifiOff } from "lucide-react";

export default function OfflinePage() {
  return (
    <main className="relative flex min-h-[100dvh] items-center justify-center overflow-hidden bg-canvas px-5 py-10">
      <div aria-hidden className="absolute left-1/2 top-1/2 h-[32rem] w-[32rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-primary-400/10" />
      <div aria-hidden className="absolute left-1/2 top-1/2 h-[24rem] w-[24rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-secondary-400/10" />

      <section className="relative w-full max-w-xl overflow-hidden rounded-[1.75rem] border border-edge-strong bg-surface/95 p-6 shadow-[0_30px_100px_rgba(0,0,0,0.35)] backdrop-blur-xl sm:p-9">
        <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-primary-400 via-primary-500 to-secondary-400" />
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image
              src="/icons/icon-192.png"
              alt=""
              width={40}
              height={40}
              className="rounded-xl"
            />
            <div>
              <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.18em] text-primary-300">Connection state</p>
              <p className="mt-0.5 text-sm font-semibold text-ink">INSIGHT / INVEST</p>
            </div>
          </div>
          <span className="flex h-10 w-10 items-center justify-center rounded-full border border-warning/25 bg-warning/10 text-warning">
            <WifiOff size={18} aria-hidden />
          </span>
        </div>

        <h1 className="mt-10 text-3xl font-semibold tracking-[-0.04em] text-ink">연결이 끊겼습니다</h1>
        <p className="mt-3 max-w-md text-sm leading-7 text-ink-secondary">
          투자 데이터는 관측 시점이 중요하므로 캐시된 숫자를 최신값처럼 표시하지 않습니다. 연결을 복구한 뒤 다시 확인해 주세요.
        </p>

        <div className="mt-8 grid gap-px overflow-hidden rounded-2xl border border-edge bg-edge sm:grid-cols-2">
          <div className="bg-raised p-4">
            <DatabaseZap size={16} className="text-primary-300" aria-hidden />
            <p className="mt-3 text-xs font-semibold text-ink">기존 데이터 보호</p>
            <p className="mt-1 text-[11px] leading-5 text-ink-muted">연결 실패로 포트폴리오나 연구 기록을 덮어쓰지 않습니다.</p>
          </div>
          <div className="bg-raised p-4">
            <RefreshCw size={16} className="text-secondary-400" aria-hidden />
            <p className="mt-3 text-xs font-semibold text-ink">복구 방법</p>
            <p className="mt-1 text-[11px] leading-5 text-ink-muted">Wi‑Fi 또는 모바일 연결을 확인한 뒤 새로 요청합니다.</p>
          </div>
        </div>

        <a href="/home" className="btn-primary mt-6 inline-flex w-full items-center justify-center gap-2 py-3">
          <RefreshCw size={16} aria-hidden />
          연결 다시 확인
        </a>
        <p className="mt-4 text-center font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">No stale investment data shown</p>
      </section>
    </main>
  );
}
