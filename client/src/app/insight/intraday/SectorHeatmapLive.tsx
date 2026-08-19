import React from "react";
import { IntradaySectorRow } from "@/state/api";
import { fmtPct } from "@/app/insight/format";

const tileColor = (chg: number) => {
  const base = chg >= 0 ? "var(--gains)" : "var(--losses)";
  const pct = Math.min(Math.abs(chg) / 3, 1) * 28 + 6; // ±3% 포화, 6~34% 틴트
  return `color-mix(in srgb, ${base} ${pct.toFixed(0)}%, transparent)`;
};

/** 섹터 히트맵 — 거래대금 내림차순, 상위 4개는 2칸 타일. */
const SectorHeatmapLive = ({ sectors }: { sectors: IntradaySectorRow[] }) => (
  <div className="card">
    <h4 className="text-base font-semibold text-ink mb-4">Sector Heatmap</h4>
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-1.5">
      {sectors.map((s, i) => (
        <div
          key={s.name}
          className={`rounded-lg p-2.5 flex flex-col justify-between min-h-[64px] ${
            i < 4 ? "col-span-2" : ""
          }`}
          style={{ backgroundColor: tileColor(s.chg_pct) }}
        >
          <p className="text-xs font-medium text-ink truncate">{s.name}</p>
          <p className={`num text-sm font-semibold ${
            s.chg_pct >= 0 ? "text-gains" : "text-losses"
          }`}>
            {fmtPct(s.chg_pct)}
          </p>
        </div>
      ))}
    </div>
  </div>
);

export default SectorHeatmapLive;
