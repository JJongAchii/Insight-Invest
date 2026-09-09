"use client";

import React, { useEffect, useRef } from "react";
import { IntradayMarketResponse } from "@/state/api";
import IntradayIndexStrip from "./IntradayIndexStrip";
import SectorHeatmapLive from "./SectorHeatmapLive";
import SectorFlowChart from "./SectorFlowChart";
import RankTables from "./RankTables";
import MyIntraday from "./MyIntraday";
import IntradaySectorMembers from "./IntradaySectorMembers";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";

/** 장중 탭 본문. 상단 배지에 지연·기준시각을 명시한다 (스펙 D4). */
const IntradayTab = ({ data, selectedSector, onSelectSector, isFetching, onRetry }: {
  data: IntradayMarketResponse;
  selectedSector: string | null;
  onSelectSector: (name: string) => void;
  isFetching: boolean;
  onRetry: () => unknown;
}) => {
  const heading = useRef<HTMLHeadingElement>(null);
  const focusSelection = useRef(false);
  const detail = data.sector_detail?.name === selectedSector ? data.sector_detail : undefined;
  useEffect(() => {
    if (!focusSelection.current) return;
    const frame = requestAnimationFrame(() => {
      // Re-align when loading finishes: a short loading panel may initially
      // leave too little page height to scroll the heading below the toolbar.
      if (!isFetching) focusSelection.current = false;
      heading.current?.focus({ preventScroll: true });
      if (heading.current && window.matchMedia("(max-width: 767px)").matches) {
        // Keep the selected heading below the sticky navigation bar.
        window.scrollTo({ top: window.scrollY + heading.current.getBoundingClientRect().top - 100, behavior: "instant" });
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [selectedSector, isFetching, detail]);
  return (
  <div className="flex flex-col gap-6">
    <div className="flex items-center gap-2 text-xs text-ink-muted">
      <span
        className="px-2 py-0.5 rounded-md font-semibold"
        style={{
          color: "var(--losses)",
          backgroundColor: "color-mix(in srgb, var(--losses) 10%, transparent)",
        }}
      >
        {data.is_open ? "장중" : "마감 스냅샷"}
      </span>
      <span>지연 시세 · {data.as_of ?? "시각 미확인"} 기준 (~20분 지연)</span>
    </div>
    <IntradayIndexStrip data={data} />
    {data.sectors && data.sectors.length > 0 && (
      <SectorHeatmapLive sectors={data.sectors} selected={selectedSector} onSelect={(name) => {
          focusSelection.current = name !== selectedSector;
          onSelectSector(name);
      }} />
    )}
    {selectedSector && <section id="intraday-sector-members" aria-label="장중 구성 종목" aria-busy={isFetching}
      className="min-w-0 overflow-clip rounded-2xl border border-edge bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 pb-2 pt-5">
        <h3 ref={heading} tabIndex={-1} className="scroll-mt-28 text-base font-semibold focus-visible:outline-2 focus-visible:outline-primary-400">
          {selectedSector} 구성 종목
        </h3>
        <button type="button" className="text-xs text-ink-secondary hover:text-ink" onClick={() => {
          const map = document.getElementById("intraday-sector-map");
          map?.querySelector<HTMLButtonElement>('button[aria-pressed="true"]')?.focus({ preventScroll: true });
          map?.scrollIntoView({ block: "start", behavior: "instant" });
        }}>섹터 다시 선택 ↑</button>
      </div>
      {detail ? <IntradaySectorMembers key={selectedSector} detail={detail} asOf={data.as_of} />
        : isFetching ? <LoadingState label="구성 종목을 확인하고 있습니다…" />
          : <ErrorState message="구성 종목을 불러오지 못했습니다" onRetry={onRetry} />}
    </section>}
    {data.sectors && data.sectors.length > 0 && <SectorFlowChart sectors={data.sectors} />}
    {data.top_value && data.top_movers && (
      <RankTables topValue={data.top_value} up={data.top_movers.up} down={data.top_movers.down} />
    )}
    {data.my && <MyIntraday my={data.my} />}
  </div>
  );
};

export default IntradayTab;
