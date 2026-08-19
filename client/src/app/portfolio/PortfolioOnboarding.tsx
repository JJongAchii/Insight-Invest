"use client";

import { ChangeEvent, useMemo, useState } from "react";
import { FileDown, FileUp, FlaskConical, Plus } from "lucide-react";

import { useAddHoldingMutation, useFetchMetaDataQuery } from "@/state/api";
import { MetaRow } from "@/app/stocksearch/types";

const TEMPLATE = "ticker,market,shares,avg_cost,target_weight_pct,thesis,invalidation,review_date\n005930,KR,10,85000,50,AI 메모리 성장,영업이익 추정 하향,2026-09-30\nAAPL,US,2,210,50,서비스 매출 성장,성장률 5% 하회,2026-10-31\n";

export default function PortfolioOnboarding({ onManual }: { onManual: () => void }) {
  const { data: rawMeta } = useFetchMetaDataQuery({});
  const [addHolding] = useAddHoldingMutation();
  const [message, setMessage] = useState("");
  const [showSample, setShowSample] = useState(false);
  const lookup = useMemo(() => {
    const map = new Map<string, MetaRow>();
    for (const row of (rawMeta as MetaRow[] | undefined) ?? []) {
      map.set(`${row.iso_code}:${row.ticker}`, row);
    }
    return map;
  }, [rawMeta]);

  const downloadTemplate = () => {
    const url = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "insight-invest-holdings-template.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const importCsv = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const lines = (await file.text()).split(/\r?\n/).filter(Boolean);
    const headers = lines[0]?.split(",").map((value) => value.trim());
    const required = ["ticker", "market", "shares", "avg_cost"];
    if (!headers || required.some((name) => !headers.includes(name))) {
      setMessage("필수 열(ticker, market, shares, avg_cost)을 확인하세요.");
      return;
    }
    let imported = 0;
    const failures: string[] = [];
    for (const line of lines.slice(1)) {
      const values = line.split(",").map((value) => value.trim());
      const row = Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""]));
      const found = lookup.get(`${row.market}:${row.ticker}`);
      const shares = Number(row.shares);
      const avgCost = Number(row.avg_cost);
      if (!found || !(shares > 0) || !(avgCost > 0)) {
        failures.push(`${row.market}:${row.ticker}`);
        continue;
      }
      await addHolding({
        meta_id: found.meta_id,
        shares,
        avg_cost: avgCost,
        currency: row.market === "KR" ? "KRW" : "USD",
        target_weight: row.target_weight_pct ? Number(row.target_weight_pct) / 100 : null,
        thesis: row.thesis,
        invalidation: row.invalidation,
        review_date: row.review_date || null,
      }).unwrap();
      imported += 1;
    }
    setMessage(`${imported}개 종목을 가져왔습니다.${failures.length ? ` 확인 필요: ${failures.join(", ")}` : ""}`);
    event.target.value = "";
  };

  return (
    <section className="card">
      <h2 className="text-lg font-semibold text-ink">Start Your Portfolio</h2>
      <p className="mt-1 text-sm text-ink-secondary">
        현재 보유량을 개시 스냅샷으로 넣거나, 아래 원장에서 입금·매수부터 기록할 수 있습니다.
      </p>
      <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
        <button onClick={onManual} className="rounded-xl border border-edge p-4 text-left hover:bg-raised">
          <Plus size={20} className="text-primary-400" aria-hidden />
          <p className="mt-3 font-semibold text-ink">수동 입력</p>
          <p className="mt-1 text-sm text-ink-muted">종목·수량·평단과 투자 논거를 한 건씩 입력</p>
        </button>
        <div className="rounded-xl border border-edge p-4">
          <FileUp size={20} className="text-primary-400" aria-hidden />
          <p className="mt-3 font-semibold text-ink">CSV 가져오기</p>
          <p className="mt-1 text-sm text-ink-muted">템플릿으로 여러 개시 포지션을 한 번에 등록</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={downloadTemplate} className="btn-ghost inline-flex items-center gap-1 px-2 py-1 text-xs">
              <FileDown size={14} aria-hidden /> 템플릿
            </button>
            <label className="btn-secondary cursor-pointer px-2 py-1 text-xs">
              CSV 선택
              <input type="file" accept=".csv,text/csv" className="sr-only" onChange={importCsv} />
            </label>
          </div>
        </div>
        <button onClick={() => setShowSample((value) => !value)} className="rounded-xl border border-edge p-4 text-left hover:bg-raised">
          <FlaskConical size={20} className="text-primary-400" aria-hidden />
          <p className="mt-3 font-semibold text-ink">샘플로 둘러보기</p>
          <p className="mt-1 text-sm text-ink-muted">실제 데이터를 저장하지 않고 화면 구조 이해</p>
        </button>
      </div>
      {message && <p className="mt-4 text-sm text-ink-secondary">{message}</p>}
      {showSample && (
        <div className="mt-4 rounded-xl bg-raised p-4 text-sm">
          <p className="font-semibold text-ink">샘플 구성 · 저장되지 않음</p>
          <p className="mt-2 text-ink-secondary">삼성전자 45% · AAPL 35% · 현금 20%</p>
          <p className="mt-1 text-ink-muted">실제 사용에서는 평가액, 미실현/실현 손익, 목표 괴리, 통화 노출과 검토일이 표시됩니다.</p>
        </div>
      )}
    </section>
  );
}
