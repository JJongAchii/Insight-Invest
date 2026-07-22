"use client";

import React, { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";

import {
  useFetchInsightFlowsTickerQuery,
  useFetchPriceHistoryQuery,
  useFetchStockDetailQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import WatchlistStar from "@/components/ui/WatchlistStar";
import HoldingButton from "@/components/HoldingButton";
import { fmtEok, fmtJo, Segmented } from "../../insight/format";
import StockPriceFlowsChart from "./StockPriceFlowsChart";

type Period = "3m" | "6m" | "1y" | "3y" | "all";
type FlowMode = "frgn" | "inst" | "both";

const PERIOD_OPTIONS: { value: Period; label: string; days: number; months: number }[] = [
  { value: "3m", label: "3M", days: 91, months: 3 },
  { value: "6m", label: "6M", days: 182, months: 6 },
  { value: "1y", label: "1Y", days: 365, months: 12 },
  { value: "3y", label: "3Y", days: 365 * 3, months: 36 },
  { value: "all", label: "ALL", days: 365 * 10, months: 120 },
];

const FLOW_OPTIONS: { id: FlowMode; label: string }[] = [
  { id: "frgn", label: "외국인" },
  { id: "inst", label: "기관" },
  { id: "both", label: "Both" },
];

/** Fractional return (0.12) → "+12.0%". */
const fmtReturn = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
};

const fmtPrice = (value: number | null | undefined, isKr: boolean): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (isKr) return `${Math.round(value).toLocaleString()}원`;
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const fmtMarketCapUsd = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
};

const returnDelta = (
  value: number | null | undefined
): "gain" | "loss" | "neutral" => {
  if (value === null || value === undefined || value === 0) return "neutral";
  return value > 0 ? "gain" : "loss";
};

const StockDetailPage = () => {
  const router = useRouter();
  const params = useParams<{ metaId: string }>();
  const metaId = Number(params?.metaId);

  const [period, setPeriod] = useState<Period>("1y");
  const [flowMode, setFlowMode] = useState<FlowMode>("frgn");

  const {
    data: detail,
    isLoading: detailLoading,
    error: detailError,
    refetch: refetchDetail,
  } = useFetchStockDetailQuery(metaId, {
    skip: !Number.isFinite(metaId) || metaId <= 0,
  });

  const periodOption =
    PERIOD_OPTIONS.find((p) => p.value === period) ?? PERIOD_OPTIONS[2];

  const dateRange = useMemo(() => {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - periodOption.days);
    return {
      startDate: startDate.toISOString().split("T")[0],
      endDate: endDate.toISOString().split("T")[0],
    };
  }, [periodOption.days]);

  const { data: priceData, isLoading: priceLoading } =
    useFetchPriceHistoryQuery(
      {
        metaId,
        startDate: dateRange.startDate,
        endDate: dateRange.endDate,
      },
      { skip: !Number.isFinite(metaId) || metaId <= 0 }
    );

  const meta = detail?.meta;
  const summary = detail?.summary;
  const isKr = meta?.iso_code === "KR";
  const isEtf = (meta?.security_type ?? "").toLowerCase() === "etf";

  const { data: flowsData } = useFetchInsightFlowsTickerQuery(
    { ticker: meta?.ticker ?? "", months: periodOption.months },
    { skip: !isKr || !meta?.ticker }
  );

  if (!Number.isFinite(metaId) || metaId <= 0) {
    return (
      <div className="card">
        <ErrorState message="잘못된 종목 ID입니다" />
      </div>
    );
  }

  if (detailError) {
    return (
      <div className="card">
        <ErrorState message="종목 정보를 불러오지 못했습니다" onRetry={refetchDetail} />
      </div>
    );
  }

  if (detailLoading || !detail || !meta || !summary) {
    return (
      <div className="card">
        <LoadingState label="종목 정보를 불러오는 중..." />
      </div>
    );
  }

  const metrics = summary.metrics;
  const flows = summary.flows_recent;
  const mktcap = summary.mktcap ?? meta.marketcap;
  const tradingViewSymbol = isKr ? `KRX-${meta.ticker}` : meta.ticker;
  const showFrgn = flowMode === "frgn" || flowMode === "both";
  const showInst = flowMode === "inst" || flowMode === "both";

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <button
            onClick={() => router.back()}
            aria-label="뒤로 가기"
            className="p-2 mt-0.5 rounded-lg bg-raised border border-edge text-ink-secondary
                       hover:bg-overlay hover:text-ink transition-colors"
          >
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="page-title">{meta.name ?? meta.ticker}</h1>
              <WatchlistStar metaId={meta.meta_id} />
              <HoldingButton
                metaId={meta.meta_id}
                ticker={meta.ticker}
                name={meta.name}
                isoCode={meta.iso_code}
                holding={detail.holding}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-ink-muted">
              <span className="num">{meta.ticker}</span>
              {meta.sector && (
                <>
                  <span>·</span>
                  <span>{meta.sector}</span>
                </>
              )}
              <span className="badge-neutral">{meta.iso_code}</span>
              {isEtf && (
                <span
                  className="badge font-semibold"
                  style={{
                    color: "var(--secondary)",
                    backgroundColor:
                      "color-mix(in srgb, var(--secondary) 12%, transparent)",
                  }}
                >
                  ETF
                </span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              {isKr && (
                <a
                  href={`https://finance.naver.com/item/main.naver?code=${meta.ticker}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                             rounded-lg bg-raised border border-edge text-ink-secondary
                             hover:bg-overlay hover:text-ink transition-colors"
                >
                  네이버 금융
                  <ExternalLink size={12} aria-hidden />
                </a>
              )}
              <a
                href={`https://www.tradingview.com/symbols/${tradingViewSymbol}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                           rounded-lg bg-raised border border-edge text-ink-secondary
                           hover:bg-overlay hover:text-ink transition-colors"
              >
                TradingView
                <ExternalLink size={12} aria-hidden />
              </a>
            </div>
          </div>
        </div>
        <div className="text-right">
          <p className="num text-3xl font-semibold text-ink">
            {fmtPrice(summary.latest_price, isKr)}
          </p>
          {summary.latest_date && (
            <p className="text-xs text-ink-muted mt-1 num">
              기준일 {summary.latest_date}
            </p>
          )}
        </div>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile
          label="시가총액"
          value={isKr ? fmtJo(mktcap) : fmtMarketCapUsd(mktcap)}
        />
        <StatTile
          label="거래대금"
          value={summary.value != null ? fmtJo(summary.value) : "—"}
        />
        <StatTile
          label="PER"
          value={summary.per != null ? summary.per.toFixed(2) : "—"}
        />
        <StatTile
          label="PBR"
          value={summary.pbr != null ? summary.pbr.toFixed(2) : "—"}
        />
        <StatTile
          label="배당수익률"
          value={summary.div != null ? `${summary.div.toFixed(2)}%` : "—"}
        />
        <StatTile
          label="YTD"
          value={fmtReturn(metrics.ytd_return)}
          deltaType={returnDelta(metrics.ytd_return)}
        />
        <StatTile
          label="1Y 수익률"
          value={fmtReturn(metrics.return_1y)}
          deltaType={returnDelta(metrics.return_1y)}
        />
        <StatTile
          label="3M 수익률"
          value={fmtReturn(metrics.return_3m)}
          deltaType={returnDelta(metrics.return_3m)}
        />
        <StatTile label="변동성" value={fmtReturn(metrics.volatility)} />
        <StatTile
          label="MDD"
          value={fmtReturn(metrics.mdd)}
          deltaType={metrics.mdd != null && metrics.mdd < 0 ? "loss" : "neutral"}
        />
      </div>

      {/* Price + flows chart */}
      <Card
        title={isKr ? "가격 · 수급" : "가격"}
        action={
          <div className="flex flex-wrap items-center gap-3">
            {isKr && (
              <Segmented
                options={FLOW_OPTIONS}
                value={flowMode}
                onChange={setFlowMode}
              />
            )}
            <Segmented
              options={PERIOD_OPTIONS.map((o) => ({
                id: o.value,
                label: o.label,
              }))}
              value={period}
              onChange={setPeriod}
            />
          </div>
        }
      >
        {priceLoading ? (
          <LoadingState label="가격 데이터를 불러오는 중..." />
        ) : priceData?.prices && priceData.prices.length > 0 ? (
          <StockPriceFlowsChart
            prices={priceData.prices}
            flows={flowsData?.rows ?? null}
            showFrgn={showFrgn}
            showInst={showInst}
            isKr={isKr}
          />
        ) : (
          <EmptyState title="가격 데이터가 없습니다" />
        )}
      </Card>

      {/* KR flow summary */}
      {isKr && flows && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              수급 요약 (20일)
              <InfoTip helpKey="signal.intensity" />
            </span>
          }
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <StatTile
              label="외국인 20일 순매수"
              value={fmtEok(flows.frgn_net_20d)}
              deltaType={returnDelta(flows.frgn_net_20d)}
            />
            <StatTile
              label="기관 20일 순매수"
              value={fmtEok(flows.inst_net_20d)}
              deltaType={returnDelta(flows.inst_net_20d)}
            />
          </div>
        </Card>
      )}
    </div>
  );
};

export default StockDetailPage;
