"use client";

import React, { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ExternalLink } from "lucide-react";

import {
  useFetchInsightFactorExposureQuery,
  useFetchInsightFlowsTickerQuery,
  useFetchPriceHistoryQuery,
  useFetchStockDetailQuery,
  useFetchStockFundamentalsQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import WatchlistStar from "@/components/ui/WatchlistStar";
import HoldingButton from "@/components/HoldingButton";
import FactorBars from "@/components/charts/FactorBars";
import { fmtEok, fmtJo, Segmented } from "../../insight/format";
import StockPriceFlowsChart from "./StockPriceFlowsChart";
import FundamentalsCard from "./FundamentalsCard";
import {
  formatDate,
  formatMarketCap,
  formatPrice,
  formatReferenceSource,
  formatShares,
} from "@/lib/market";

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

  // Factor percentiles for this KR name (server skips US/ETF via `note`).
  const factorArg = useMemo(() => [metaId], [metaId]);
  const { data: factorData } = useFetchInsightFactorExposureQuery(factorArg, {
    skip: !isKr || isEtf || !Number.isFinite(metaId) || metaId <= 0,
  });

  const { data: fundamentalData, isLoading: fundamentalLoading } =
    useFetchStockFundamentalsQuery(metaId, {
      skip: isKr || isEtf || !Number.isFinite(metaId) || metaId <= 0,
    });

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
  const hasFundSizeContract = meta.fund_size !== undefined;
  const size = isEtf && hasFundSizeContract ? (meta.fund_size ?? null) : mktcap;
  let sizeLabel = "Market Cap";
  if (isEtf && hasFundSizeContract) {
    sizeLabel =
      meta.fund_size_source === "estimate_close_x_share_class_shares"
        ? "Fund Size (est.)"
        : "Fund Size";
  }
  const sizeSource = isEtf ? meta.fund_size_source : meta.marketcap_source;
  const referenceTypeLabel =
    meta.security_subtype &&
    meta.security_subtype.toUpperCase() !== meta.security_type?.toUpperCase()
      ? `${meta.security_type ?? "—"} · ${meta.security_subtype}`
      : (meta.security_type ?? "—");
  const tradingViewSymbol = isKr ? `KRX-${meta.ticker}` : meta.ticker;
  const showFrgn = flowMode === "frgn" || flowMode === "both";
  const showInst = flowMode === "inst" || flowMode === "both";
  // Vercel과 Lambda가 동시에 교체되는 짧은 구간에는 구 API 응답에 계약 필드가
  // 없을 수 있다. 화면을 깨뜨리지 않고 종전 가격 라벨로 안전하게 폴백한다.
  const seriesContract = priceData?.series_contract ?? summary.series_contract ?? {
    series_type: isKr ? "split_adjusted_price" as const : "total_return_index" as const,
    label: isKr ? "Adjusted Price" as const : "Total Return" as const,
    return_basis: isKr
      ? "split_adjusted_price_return_ex_cash_distributions"
      : "split_adjusted_total_return_including_cash_distributions",
    capital_actions: "included",
    cash_distributions: isKr ? "excluded" as const : "included" as const,
    calculation_version: "legacy_api_fallback",
    warning: isKr ? "현금배당은 포함하지 않은 가격수익률입니다." : null,
  };

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
                  {meta.security_subtype && meta.security_subtype !== "ETF"
                    ? `ETF · ${meta.security_subtype}`
                    : "ETF"}
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
            {formatPrice(summary.latest_price, meta.iso_code)}
          </p>
          {summary.latest_date && (
            <p className="text-xs text-ink-muted mt-1 num">
              가격 기준일 {formatDate(summary.latest_date)}
            </p>
          )}
          <p className="mt-1 text-xs text-ink-muted">
            {seriesContract.label} · {seriesContract.cash_distributions === "included"
              ? "현금분배 포함"
              : seriesContract.cash_distributions === "implicit_in_reference_price"
                ? "분배락 기준가격 반영"
                : "현금분배 제외"}
          </p>
        </div>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatTile
          label={sizeLabel}
          value={isKr ? fmtJo(size) : formatMarketCap(size, meta.iso_code)}
        />
        {!isKr && meta.shares_outstanding != null && (
          <StatTile label="Shares Outstanding" value={formatShares(meta.shares_outstanding)} />
        )}
        {isKr && <StatTile
          label="Trading Value"
          value={summary.value != null ? fmtJo(summary.value) : "—"}
        />}
        {isKr && <StatTile
          label="PER"
          value={summary.per != null ? summary.per.toFixed(2) : "—"}
        />}
        {isKr && <StatTile
          label="PBR"
          value={summary.pbr != null ? summary.pbr.toFixed(2) : "—"}
        />}
        {isKr && <StatTile
          label="Dividend Yield"
          value={summary.div != null ? `${summary.div.toFixed(2)}%` : "—"}
        />}
        <StatTile
          label="YTD"
          value={fmtReturn(metrics.ytd_return)}
          deltaType={returnDelta(metrics.ytd_return)}
        />
        <StatTile
          label="1Y Return"
          value={fmtReturn(metrics.return_1y)}
          deltaType={returnDelta(metrics.return_1y)}
        />
        <StatTile
          label="3M Return"
          value={fmtReturn(metrics.return_3m)}
          deltaType={returnDelta(metrics.return_3m)}
        />
        <StatTile label="Volatility" value={fmtReturn(metrics.volatility)} />
        <StatTile
          label="MDD"
          value={fmtReturn(metrics.mdd)}
          deltaType={metrics.mdd != null && metrics.mdd < 0 ? "loss" : "neutral"}
        />
      </div>

      {!isKr && (
        <div className="rounded-xl border border-edge bg-raised px-4 py-3 text-xs text-ink-secondary">
          <p>
            <span className="font-semibold text-ink">Reference Data</span>
            {meta.reference_as_of
              ? ` · 기준 ${formatDate(meta.reference_as_of)}`
              : " · 기준일 없음"}
          </p>
          <p className="mt-1 text-ink-muted">
            Type {referenceTypeLabel}
            {meta.shares_outstanding != null
              ? ` · Shares ${formatShares(meta.shares_outstanding)}`
              : ""}
            {meta.weighted_shares_outstanding != null
              ? ` · Weighted ${formatShares(meta.weighted_shares_outstanding)}`
              : ""}
          </p>
          {sizeSource && (
            <p className="mt-1 text-ink-muted">
              Size Source {formatReferenceSource(sizeSource)}
            </p>
          )}
          {meta.fund_size_source === "estimate_close_x_share_class_shares" && (
            <p className="mt-1 text-ink-muted">
              Fund Size는 최근 종가×발행좌수 추정치이며 운용사가 보고한 AUM은 아닙니다.
              {meta.fund_size_as_of ? ` 가격 기준 ${formatDate(meta.fund_size_as_of)}` : ""}
            </p>
          )}
          {meta.marketcap_source === "massive_close_x_weighted_shares" && (
            <p className="mt-1 text-ink-muted">
              Market Cap은 최근 종가와 Massive 가중 발행주식수로 계산했습니다.
              {meta.marketcap_as_of ? ` 가격 기준 ${formatDate(meta.marketcap_as_of)}` : ""}
            </p>
          )}
        </div>
      )}

      {isKr && !isEtf && summary.valuation && (
        <div className="rounded-xl border border-edge bg-raised px-4 py-3 text-xs text-ink-secondary">
          <p>
            <span className="font-semibold text-ink">Valuation</span>
            {summary.valuation.as_of ? ` · 기준 ${formatDate(summary.valuation.as_of)}` : " · 기준일 없음"}
            {` · ${summary.valuation.calculation_version}`}
          </p>
          <p className="mt-1 text-ink-muted">
            같은 날짜의 KRX 종가·시가총액·주식수와 EPS/BPS/DPS로 PER·PBR·Dividend Yield를 재계산해 원천값과 대조합니다.
          </p>
          {summary.valuation.missing_reasons.length > 0 && (
            <p className="mt-1 text-warning">{summary.valuation.missing_reasons.join(" ")}</p>
          )}
        </div>
      )}

      {!isKr && !isEtf && (
        <FundamentalsCard
          facts={fundamentalData?.facts}
          asOf={fundamentalData?.as_of}
          note={fundamentalData?.note}
          isLoading={fundamentalLoading}
        />
      )}

      {/* Price + flows chart */}
      <Card
        title={isKr ? "Price & Flows" : "Price"}
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
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-raised px-3 py-2 text-xs">
              <span className="font-semibold text-ink">{seriesContract.label}</span>
              <span className="text-ink-muted">{seriesContract.calculation_version}</span>
              {seriesContract.warning && <span className="w-full text-warning">{seriesContract.warning}</span>}
            </div>
            <StockPriceFlowsChart
              prices={priceData.prices}
              flows={flowsData?.rows ?? null}
              showFrgn={showFrgn}
              showInst={showInst}
              isKr={isKr}
            />
          </div>
        ) : (
          <EmptyState title="가격 데이터가 없습니다" />
        )}
      </Card>

      {/* KR flow summary */}
      {isKr && flows && (
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              Flow Summary · 20D
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

      {/* Factor scores (KR only; hidden for US/ETF or when server skips) */}
      {isKr &&
        !isEtf &&
        factorData &&
        !factorData.note &&
        factorData.exposures.length > 0 && (
          <Card
            title={
              <span className="inline-flex items-center gap-1.5">
                Factor Exposure
                <InfoTip helpKey="factor.exposure" />
              </span>
            }
          >
            <div className="max-w-md">
              <FactorBars exposures={factorData.exposures} compact />
            </div>
          </Card>
        )}
    </div>
  );
};

export default StockDetailPage;
