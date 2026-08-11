import React from "react";
import { IntradayMarketResponse } from "@/state/api";
import IntradayIndexStrip from "./IntradayIndexStrip";

/** 장중 탭 본문. 상단 배지에 지연·기준시각을 명시한다 (스펙 D4). */
const IntradayTab = ({ data }: { data: IntradayMarketResponse }) => (
  <div className="flex flex-col gap-6">
    <div className="flex items-center gap-2 text-xs text-ink-muted">
      <span
        className="px-2 py-0.5 rounded-md font-semibold"
        style={{
          color: "var(--losses)",
          backgroundColor: "color-mix(in srgb, var(--losses) 10%, transparent)",
        }}
      >
        {data.is_open ? "🔴 장중" : "15:30 마감"}
      </span>
      <span>지연 시세 · {data.as_of?.slice(-5)} 기준 (~20분 지연)</span>
    </div>
    <IntradayIndexStrip data={data} />
  </div>
);

export default IntradayTab;
