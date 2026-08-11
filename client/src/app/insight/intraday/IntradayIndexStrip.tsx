import React from "react";
import { IntradayMarketResponse } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";
import Sparkline from "./Sparkline";

/** 장중 지수·브레드스 스트립 — data.active가 참일 때만 렌더된다. */
const IntradayIndexStrip = ({ data }: { data: IntradayMarketResponse }) => {
  const breadth = data.breadth;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {(data.indices ?? []).map((idx) => (
        <div key={idx.key} className="card flex items-center justify-between gap-2">
          <div>
            <p className="metric-label">{idx.key}</p>
            <div className="flex items-baseline gap-2">
              <p className="metric-value">
                {idx.level.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </p>
              <span className={`text-sm ${signClass(idx.chg_pct)}`}>
                {fmtPct(idx.chg_pct)}
              </span>
            </div>
          </div>
          <Sparkline
            points={idx.sparkline.map((p) => p.level)}
            color={
              (idx.chg_pct ?? 0) >= 0 ? "var(--gains)" : "var(--losses)"
            }
          />
        </div>
      ))}
      {breadth && (
        <div className="card flex flex-col justify-between gap-1">
          <p className="metric-label">시장폭 (KR 전 종목)</p>
          <div className="flex items-baseline gap-3 text-sm">
            <span className="text-gains font-semibold">▲ {breadth.advancers}</span>
            <span className="text-losses font-semibold">▼ {breadth.decliners}</span>
            <span className="text-ink-muted">− {breadth.unchanged}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntradayIndexStrip;
