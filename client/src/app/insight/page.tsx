"use client";

import React, { useState } from "react";
import { InsightMarket } from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import IndexBreadthStrip from "./IndexBreadthStrip";
import FlowsSection from "./FlowsSection";
import SectorSection from "./SectorSection";
import ValuationSection from "./ValuationSection";
import SignalsSection from "./SignalsSection";
import BreadthHistory from "./BreadthHistory";

/** KR market insight dashboard: index/breadth strip, investor flows, signals, breadth history. */
const InsightPage = () => {
  // Market toggle shared by the breadth strip and the breadth history section.
  const [market, setMarket] = useState<InsightMarket>("KOSPI");

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="KR Market Insight"
        description="수급·시장폭·신호 — KRX 전 종목 데이터 기반"
      />

      {/* 1. Index & breadth strip */}
      <IndexBreadthStrip market={market} onMarketChange={setMarket} />

      {/* 2. Foreign/Institution flows */}
      <FlowsSection />

      {/* 3. Sector heatmap & rotation */}
      <SectorSection />

      {/* 4. Market valuation */}
      <ValuationSection />

      {/* 5. Flow signals */}
      <SignalsSection />

      {/* 6. Breadth history */}
      <BreadthHistory market={market} onMarketChange={setMarket} />
    </div>
  );
};

export default InsightPage;
