"use client";

import React, { useState } from "react";
import { IoBriefcase } from "react-icons/io5";
import { Plus } from "lucide-react";

import {
  HoldingPosition,
  useFetchHoldingsQuery,
  useRemoveHoldingMutation,
} from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { fmtJo } from "@/app/insight/format";
import {
  fmtFracPct,
  fmtSignedJo,
  pnlDeltaType,
  signClassNum,
} from "./format";
import PortfolioTable from "./PortfolioTable";
import AllocationCard from "./AllocationCard";
import HoldingModal from "./HoldingModal";

const PortfolioPage = () => {
  const { data, isLoading, error, refetch } = useFetchHoldingsQuery();
  const [removeHolding] = useRemoveHoldingMutation();

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
        title="My Portfolio"
        description="실제 보유 포지션·손익·노출"
        actions={
          <button onClick={openAdd} className="btn-primary inline-flex items-center gap-1.5">
            <Plus size={16} aria-hidden />
            종목 추가
          </button>
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
        <div className="card">
          <EmptyState
            icon={<IoBriefcase className="w-7 h-7" aria-hidden />}
            title="보유 종목을 추가하세요"
            hint={
              <button
                onClick={openAdd}
                className="text-primary-400 hover:underline"
              >
                첫 종목 추가하기 →
              </button>
            }
          />
        </div>
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

          {/* Holdings table */}
          <Card title="보유 종목">
            <PortfolioTable
              positions={positions}
              onEdit={openEdit}
              onRemove={handleRemove}
            />
          </Card>

          {/* Allocation breakdown */}
          <AllocationCard summary={summary} />
        </>
      )}

      <HoldingModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        editing={editing}
      />
    </div>
  );
};

export default PortfolioPage;
