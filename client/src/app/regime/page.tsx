"use client";

import React, { useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import PhaseQuadrant from "./PhaseQuadrant";
import RiskGauge from "./RiskGauge";
import PhaseTimeline from "./PhaseTimeline";
import PhasePerformance from "./PhasePerformance";
import USIndicators from "./USIndicators";
import KoreaMacro from "./KoreaMacro";

type MacroTab = "us" | "kr";

const TABS: { id: MacroTab; label: string }[] = [
  { id: "us", label: "US Indicators" },
  { id: "kr", label: "Korea" },
];

const Regime = () => {
  const [tab, setTab] = useState<MacroTab>("us");

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="Market Regime"
        description="Growth/inflation phase, risk-off gauge, and US·KR macro indicators"
      />

      {/* Top row: phase quadrant + risk gauge */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <PhaseQuadrant className="lg:col-span-2" />
        <RiskGauge />
      </div>

      {/* Phase timeline */}
      <PhaseTimeline />

      {/* Phase performance table */}
      <PhasePerformance />

      {/* Macro indicators: US | Korea */}
      <div className="flex flex-col gap-6">
        <div className="flex items-center gap-1 p-1 rounded-xl bg-raised border border-edge self-start">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                tab === t.id
                  ? "bg-surface text-ink shadow-sm"
                  : "text-ink-secondary hover:text-ink"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "us" ? <USIndicators /> : <KoreaMacro />}
      </div>
    </div>
  );
};

export default Regime;
