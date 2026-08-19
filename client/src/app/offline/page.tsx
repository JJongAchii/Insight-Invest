import Image from "next/image";

export default function OfflinePage() {
  return (
    <main className="flex min-h-[100dvh] items-center justify-center px-6 text-center">
      <section className="max-w-sm">
        <Image
          src="/icons/icon-192.png"
          alt=""
          width={72}
          height={72}
          className="mx-auto mb-5 rounded-2xl"
        />
        <h1 className="text-2xl font-semibold text-ink">You’re Offline</h1>
        <p className="mt-3 leading-6 text-ink-muted">
          투자 데이터는 최신성이 중요해 오프라인 값을 표시하지 않습니다. 연결을 확인한
          뒤 다시 시도해주세요.
        </p>
        <a href="/home" className="btn-primary mt-6 inline-block">
          Try Again
        </a>
      </section>
    </main>
  );
}
