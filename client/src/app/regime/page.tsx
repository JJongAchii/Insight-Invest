"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import PhaseQuadrant from "./PhaseQuadrant";
import RiskGauge from "./RiskGauge";
import PhaseTimeline from "./PhaseTimeline";
import PhasePerformance from "./PhasePerformance";
import USIndicators from "./USIndicators";
import KoreaMacro from "./KoreaMacro";

function RegimeContent() {
  const params = useSearchParams();
  const section = params.get("section") === "phase" ? "phase" : "indicators";
  const country = params.get("country") === "kr" ? "kr" : "us";
  const [historyOpen, setHistoryOpen] = useState(false);
  const updateView = (values: Record<string, string>) => {
    const url = new URL(window.location.href);
    Object.entries(values).forEach(([key, value]) =>
      url.searchParams.set(key, value),
    );
    window.history.pushState(null, "", url);
  };

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        title="경제 · 매크로"
        description="금리·물가·고용·환율의 관측값과 흐름을 확인하고, 경기 국면의 해석으로 연결합니다."
      />
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-edge pb-4">
        <div className="segmented-control" aria-label="경제 분석 항목">
          <button
            type="button"
            aria-pressed={section === "indicators"}
            onClick={() => updateView({ section: "indicators" })}
          >
            경제 지표
          </button>
          <button
            type="button"
            aria-pressed={section === "phase"}
            onClick={() => updateView({ section: "phase" })}
          >
            경기 국면 · 위험
          </button>
        </div>
        {section === "indicators" && (
          <div className="flex gap-2" aria-label="경제 지표 국가">
            <button
              type="button"
              className="filter-chip"
              aria-pressed={country === "us"}
              onClick={() => updateView({ country: "us" })}
            >
              미국 · FRED
            </button>
            <button
              type="button"
              className="filter-chip"
              aria-pressed={country === "kr"}
              onClick={() => updateView({ country: "kr" })}
            >
              한국 · ECOS / OECD
            </button>
          </div>
        )}
      </div>
      {section === "indicators" ? (
        <>
          <p className="text-sm leading-6 text-ink-secondary">
            지표마다 발표 주기가 다릅니다. 기준일과 단위를 함께 확인하세요.
          </p>
          {country === "us" ? <USIndicators /> : <KoreaMacro />}
        </>
      ) : (
        <>
          <section className="space-y-4" aria-labelledby="regime-current">
            <div>
              <h2 id="regime-current" className="text-lg font-semibold">
                성장·물가와 위험 압력
              </h2>
              <p className="mt-1 text-sm leading-6 text-ink-secondary">
                성장과 물가의 방향으로 경기의 위치를 보고, 시장 위험 지표를 함께
                살펴봅니다.
              </p>
            </div>
            <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-3">
              <PhaseQuadrant className="lg:col-span-2" />
              <RiskGauge />
            </div>
          </section>
          <section className="space-y-4" aria-labelledby="regime-history">
            <h2 id="regime-history" className="text-lg font-semibold">
              경기 국면의 변화
            </h2>
            <PhaseTimeline />
          </section>
          <details
            className="rounded-xl border border-edge bg-surface p-5"
            onToggle={(event) => setHistoryOpen(event.currentTarget.open)}
          >
            <summary className="cursor-pointer text-sm font-medium text-ink-secondary">
              과거 같은 국면의 자산 흐름 살펴보기
            </summary>
            {historyOpen && (
              <div className="mt-5">
                <p className="mb-4 text-xs leading-6 text-ink-muted">
                  과거 같은 국면에 해당했던 달의 통계입니다. 표본 수를 함께
                  확인하세요.
                </p>
                <PhasePerformance />
              </div>
            )}
          </details>
        </>
      )}
    </div>
  );
}

export default function Regime() {
  return (
    <Suspense fallback={<LoadingState label="경제 화면을 준비하는 중…" />}>
      <RegimeContent />
    </Suspense>
  );
}
