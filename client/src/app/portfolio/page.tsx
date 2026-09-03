"use client";

import React, { useState } from "react";
import { Plus } from "lucide-react";

import {
  HoldingPosition,
  useFetchHoldingsQuery,
  useFetchPortfolioLedgerQuery,
  useRemoveHoldingMutation,
} from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { fmtJo } from "@/app/insight/format";
import {
  fmtFracPct,
  fmtSignedJo,
  pnlDeltaType,
  signClassNum,
} from "./format";
import PortfolioTable from "./PortfolioTable";
import AllocationCard from "./AllocationCard";
import RiskCard from "./RiskCard";
import FactorExposureCard from "./FactorExposureCard";
import HoldingModal from "./HoldingModal";
import LedgerPanel from "./LedgerPanel";
import PortfolioOnboarding from "./PortfolioOnboarding";
import PortfolioXRay from "./PortfolioXRay";

const PortfolioPage = () => {
  const { data, isLoading, error, refetch } = useFetchHoldingsQuery();
  const [removeHolding] = useRemoveHoldingMutation();
  const { data: ledger } = useFetchPortfolioLedgerQuery();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<HoldingPosition | null>(null);

  const openAdd = () => {
    setEditing(null);
    setModalOpen(true);
  };
  const openEdit = (position: HoldingPosition) => {
    setEditing(position);
    setModalOpen(true);
  };
  const handleRemove = (metaId: number) => {
    removeHolding(metaId);
  };

  const positions = data?.positions ?? [];
  const summary = data?.summary;
  const unpriced = positions.filter((position) => position.market_value_krw == null);

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        eyebrow="Portfolio ledger"
        title="내 포트폴리오"
        description="평가액보다 먼저 쏠림과 목표 괴리를 확인하고, 거래 원장과 투자 논거를 한 흐름에서 관리합니다."
        meta={
          <>
            <span>{summary ? `${summary.n_positions}개 포지션` : "포지션 확인 중"}</span>
            <span>·</span>
            <span>{summary?.valuation_complete ? "전체 가격 반영" : "일부 가격 확인 필요"}</span>
          </>
        }
        actions={
          (ledger?.summary.events_count ?? 0) === 0 ? <button onClick={openAdd} className="btn-primary inline-flex items-center gap-1.5">
            <Plus size={16} aria-hidden />
            기초 보유 추가
          </button> : undefined
        }
      />

      {error ? (
        <div className="card">
          <ErrorState
            message="보유 정보를 불러오지 못했습니다"
            onRetry={refetch}
          />
        </div>
      ) : isLoading || !data ? (
        <div className="card">
          <LoadingState label="포트폴리오를 불러오는 중..." />
        </div>
      ) : positions.length === 0 || !summary ? (
        <PortfolioOnboarding onManual={openAdd} />
      ) : (
        <>
          {summary.unpriced_positions > 0 && (
            <div role="alert" className="rounded-xl border border-[var(--chart-4)] bg-surface px-4 py-3">
              <p className="text-sm font-semibold text-ink">가격을 확인할 수 없는 보유종목이 있습니다</p>
              <p className="mt-1 text-sm text-ink-secondary">
                {unpriced.map((position) => position.ticker).join(", ")} · 해당 종목은 평가액·손익·비중 합계에서 제외됩니다.
              </p>
            </div>
          )}

          <div
            className="scrollbar-hidden -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
            role="group"
            aria-label="포트폴리오 요약"
            tabIndex={0}
          >
            <section className="metric-strip min-w-[50rem] grid-cols-5 sm:min-w-0" aria-label="포트폴리오 요약">
            <StatTile
              label={summary.valuation_complete ? "총 평가액" : "가격 반영 평가액"}
              value={summary.priced_positions > 0 ? fmtJo(summary.total_value_krw) : "—"}
            />
            <StatTile
              label="누적 손익"
              helpKey="portfolio.pnl"
              value={
                <span className={signClassNum(summary.total_pnl_krw)}>
                  {summary.priced_positions > 0 ? fmtSignedJo(summary.total_pnl_krw) : "—"}
                </span>
              }
              delta={summary.priced_positions > 0 ? fmtFracPct(summary.total_pnl_pct) : "—"}
              deltaType={pnlDeltaType(summary.total_pnl_krw)}
            />
            <StatTile
              label="오늘 손익"
              value={summary.priced_positions > 0 ? fmtSignedJo(summary.day_pnl_krw) : "—"}
              deltaType={pnlDeltaType(summary.day_pnl_krw)}
            />
            <StatTile label="보유 종목" value={`${summary.n_positions}개`} />
            <StatTile
              label="최대 단일 비중"
              helpKey="portfolio.hhi"
              value={summary.top_weight == null ? "—" : `${(summary.top_weight * 100).toFixed(1)}%`}
              sub={summary.hhi == null ? undefined : <span className="num">HHI {summary.hhi.toFixed(2)}</span>}
            />
            </section>
          </div>

          {summary.target_total != null && Math.abs(summary.target_total - 1) > 0.005 && (
            <div className="rounded-xl border border-edge px-4 py-3 text-sm text-ink-secondary">
              설정된 목표 비중 합계가 {(summary.target_total * 100).toFixed(1)}%입니다.
              투자자산 기준 100%가 되도록 확인하세요.
            </div>
          )}

          <PortfolioXRay positions={positions} summary={summary} />

          <Card
            title="보유 포지션"
            action={<span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">비중순 · 행을 눌러 종목 보기</span>}
          >
            <PortfolioTable
              positions={positions}
              onEdit={openEdit}
              onRemove={handleRemove}
              ledgerStarted={(ledger?.summary.events_count ?? 0) > 0}
            />
          </Card>

          <AllocationCard summary={summary} />

          <RiskCard />

          <FactorExposureCard positions={positions} />
        </>
      )}

      <LedgerPanel />

      <HoldingModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        editing={editing}
        ledgerStarted={(ledger?.summary.events_count ?? 0) > 0}
      />
    </div>
  );
};

export default PortfolioPage;
