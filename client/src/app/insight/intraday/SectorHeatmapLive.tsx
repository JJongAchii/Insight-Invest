import { ArrowDownRight, Check } from "lucide-react";
import { IntradaySectorRow } from "@/state/api";
import { fmtJo, fmtPct, signClass } from "@/app/insight/format";

const tileColor = (chg: number | null) => {
  if (chg == null) return "var(--surface-raised)";
  const base = chg >= 0 ? "var(--gains)" : "var(--losses)";
  const pct = Math.min(Math.abs(chg) / 3, 1) * 28 + 6;
  return `color-mix(in srgb, ${base} ${pct.toFixed(0)}%, transparent)`;
};

export default function SectorHeatmapLive({ sectors, selected, onSelect }: {
  sectors: IntradaySectorRow[];
  selected: string | null;
  onSelect: (name: string) => void;
}) {
  return <section id="intraday-sector-map" className="card scroll-mt-24" aria-label="장중 섹터 현황">
    <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
      <div><h3 className="text-base font-semibold text-ink">장중 섹터 현황</h3>
        <p className="mt-1 text-xs leading-5 text-ink-muted">섹터를 누르면 구성 종목을 볼 수 있습니다.</p></div>
      <span className="text-[11px] text-ink-muted">시총 가중 등락률 · 거래대금 순</span>
    </div>
    <div className="-m-1 grid max-h-[360px] grid-cols-2 gap-2 overflow-y-auto p-1 sm:max-h-[500px] sm:grid-cols-4 lg:grid-cols-6">
      {sectors.map((s, i) => <button key={s.name} type="button"
        aria-label={`${s.name} 구성 종목 보기`} aria-pressed={selected === s.name}
        aria-controls={selected === s.name ? "intraday-sector-members" : undefined}
        onClick={() => onSelect(s.name)}
        className={`flex min-h-[100px] min-w-0 flex-col justify-between gap-3 rounded-lg border p-3 text-left transition-colors hover:border-ink-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-400 ${selected === s.name ? "border-primary-400 ring-1 ring-primary-400" : "border-transparent"} ${i < 4 ? "sm:col-span-2" : ""}`}
        style={{ backgroundColor: tileColor(s.chg_pct) }}>
        <span className="flex items-start justify-between gap-1 text-xs font-medium text-ink">
          <span className="break-keep">{s.name}</span>
          {selected === s.name ? <Check size={14} className="shrink-0" /> : <ArrowDownRight size={14} className="shrink-0 text-ink-muted" />}
        </span>
        <span className="flex flex-wrap items-end justify-between gap-1">
          <span className={`text-base font-semibold ${signClass(s.chg_pct)}`}>{fmtPct(s.chg_pct)}</span>
          <span className="num text-[10px] text-ink-secondary">{s.n}종목 · {fmtJo(s.value_krw)}</span>
        </span>
      </button>)}
    </div>
  </section>;
}
