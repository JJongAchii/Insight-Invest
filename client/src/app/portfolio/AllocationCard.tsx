"use client";

import React from "react";

import { HoldingsSummary } from "@/state/api";
import Card from "@/components/ui/Card";
import WeightBar, { WeightBarItem } from "@/components/charts/WeightBar";

interface AllocationCardProps {
  summary: HoldingsSummary;
}

/** Two horizontal allocation breakdowns: sector and market (KR/US). */
const AllocationCard: React.FC<AllocationCardProps> = ({ summary }) => {
  const sectorItems: WeightBarItem[] = summary.sector_alloc.map((s) => ({
    label: s.sector || "기타",
    value: s.weight,
  }));

  const marketItems: WeightBarItem[] = summary.market_alloc.map((m) => ({
    label: m.label,
    value: m.weight,
  }));

  return (
    <Card title="배분 노출">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div>
          <h4 className="metric-label mb-3">섹터 배분</h4>
          {sectorItems.length > 0 ? (
            <WeightBar items={sectorItems} />
          ) : (
            <p className="text-sm text-ink-muted">데이터 없음</p>
          )}
        </div>
        <div>
          <h4 className="metric-label mb-3">시장 배분</h4>
          {marketItems.length > 0 ? (
            <WeightBar items={marketItems} />
          ) : (
            <p className="text-sm text-ink-muted">데이터 없음</p>
          )}
        </div>
      </div>
    </Card>
  );
};

export default AllocationCard;
