"use client";

import React, { useState } from "react";
import { BarChart3, Crosshair, History } from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";
import { useFetchRegimeGaugeQuery, useFetchRegimePhaseQuery } from "@/state/api";
import PhaseQuadrant from "./PhaseQuadrant";
import RiskGauge from "./RiskGauge";
import PhaseTimeline from "./PhaseTimeline";
import PhasePerformance from "./PhasePerformance";
import USIndicators from "./USIndicators";
import KoreaMacro from "./KoreaMacro";

type MacroTab = "us" | "kr";

const TABS: { id: MacroTab; label: string }[] = [
  { id: "us", label: "미국 지표" },
  { id: "kr", label: "한국 지표" },
];

const ObservatorySection = ({
  code,
  title,
  description,
  icon: Icon,
  children,
}: {
  code: string;
  title: string;
  description: string;
  icon: typeof Crosshair;
  children: React.ReactNode;
}) => (
  <section className="space-y-4" aria-labelledby={`regime-${code}`}>
    <header className="grid gap-3 border-t border-edge pt-6 md:grid-cols-[3rem_minmax(0,1fr)_minmax(260px,0.8fr)] md:items-start">
      <span className="flex h-9 w-9 items-center justify-center rounded-full border border-primary-400/30 bg-primary-500/10 text-primary-300">
        <Icon size={16} aria-hidden />
      </span>
      <div>
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">
          Lens {code}
        </p>
        <h2 id={`regime-${code}`} className="mt-1 text-xl font-semibold tracking-[-0.025em] text-ink">
          {title}
        </h2>
      </div>
      <p className="text-sm leading-6 text-ink-muted md:text-right">{description}</p>
    </header>
    {children}
  </section>
);

const Regime = () => {
  const [tab, setTab] = useState<MacroTab>("us");
  const { data: phaseData } = useFetchRegimePhaseQuery();
  const { data: gaugeData } = useFetchRegimeGaugeQuery();
  const current = phaseData?.current;

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        eyebrow="Regime map"
        title="시장 국면"
        description="한 단어의 국면 판단보다 성장·물가의 방향, 위험 압력, 원 관측치를 차례로 확인합니다."
        meta={
          <>
            <span className="inline-block min-w-[5.75rem]">{current?.phase ?? "phase pending"}</span>
            <span>·</span>
            <span className="inline-block min-w-[5.75rem]">phase {current?.as_of ?? "—"}</span>
            <span>·</span>
            <span className="inline-block min-w-[5rem]">risk {gaugeData ? Math.round(gaugeData.score) : "—"}/100</span>
          </>
        }
      />

      <ObservatorySection
        code="01"
        title="현재 좌표"
        description="성장과 물가의 방향을 먼저 배치하고, 별도 위험 점수로 시장의 방어 압력을 겹쳐 봅니다."
        icon={Crosshair}
      >
        <div className="relative grid grid-cols-1 gap-6 lg:grid-cols-3">
          <span
            aria-hidden
            className="absolute -top-px left-8 hidden h-px w-28 bg-gradient-to-r from-primary-400 to-secondary-400 lg:block"
          />
          <PhaseQuadrant className="min-h-[29rem] lg:col-span-2" />
          <RiskGauge className="min-h-[34rem]" />
        </div>
      </ObservatorySection>

      <ObservatorySection
        code="02"
        title="좌표의 이동"
        description="최신값의 라벨에 고정되지 않도록 성장·물가의 장기 경로와 최근 국면 지속 기간을 함께 봅니다."
        icon={History}
      >
        <PhaseTimeline />
      </ObservatorySection>

      <ObservatorySection
        code="03"
        title="역사적 맥락"
        description="현재 국면과 같았던 달의 자산 성과를 참고하되, 표본 수와 승률을 예측값처럼 읽지 않습니다."
        icon={BarChart3}
      >
        <PhasePerformance />
      </ObservatorySection>

      <ObservatorySection
        code="04"
        title="원 관측치"
        description="국면을 만든 미국 지표와 포트폴리오의 원화 환경을 설명하는 한국 지표를 분리해 검산합니다."
        icon={Crosshair}
      >
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-2 sm:flex-row sm:items-center sm:justify-between">
            <p className="px-2 text-xs text-ink-muted">관측 시장 선택</p>
            <div className="segmented-control" aria-label="거시 지표 국가">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  aria-pressed={tab === t.id}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {tab === "us" ? <USIndicators /> : <KoreaMacro />}
        </div>
      </ObservatorySection>
    </div>
  );
};

export default Regime;
