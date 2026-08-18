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

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="나의 포트폴리오"
        description="보유 포지션·거래 원장·현금·손익·통화 노출"
        actions={
          (ledger?.summary.events_count ?? 0) === 0 ? <button onClick={openAdd} className="btn-primary inline-flex items-center gap-1.5">
            <Plus size={16} aria-hidden />
            개시 종목 추가
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
          {/* Summary tiles */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <StatTile label="총 평가액" value={fmtJo(summary.total_value_krw)} />
            <StatTile
              label="총 손익"
              helpKey="portfolio.pnl"
              value={
                <span className={signClassNum(summary.total_pnl_krw)}>
                  {fmtSignedJo(summary.total_pnl_krw)}
                </span>
              }
              delta={fmtFracPct(summary.total_pnl_pct)}
              deltaType={pnlDeltaType(summary.total_pnl_krw)}
            />
            <StatTile
              label="일간 손익"
              value={fmtSignedJo(summary.day_pnl_krw)}
              deltaType={pnlDeltaType(summary.day_pnl_krw)}
            />
            <StatTile label="종목수" value={summary.n_positions} />
            <StatTile
              label="집중도"
              helpKey="portfolio.hhi"
              value={`${(summary.top_weight * 100).toFixed(1)}%`}
              sub={<span className="num">HHI {summary.hhi.toFixed(2)}</span>}
            />
          </div>

          {summary.target_total != null && Math.abs(summary.target_total - 1) > 0.005 && (
            <div className="rounded-xl border border-edge px-4 py-3 text-sm text-ink-secondary">
              설정된 목표 비중 합계가 {(summary.target_total * 100).toFixed(1)}%입니다.
              투자자산 기준 100%가 되도록 확인하세요.
            </div>
          )}

          {/* Holdings table */}
          <Card title="보유 종목">
            <PortfolioTable
              positions={positions}
              onEdit={openEdit}
              onRemove={handleRemove}
              ledgerStarted={(ledger?.summary.events_count ?? 0) > 0}
            />
          </Card>

          {/* Allocation breakdown */}
          <AllocationCard summary={summary} />

          {/* Portfolio risk summary */}
          <RiskCard />

          {/* Portfolio factor exposure (KR holdings only) */}
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
