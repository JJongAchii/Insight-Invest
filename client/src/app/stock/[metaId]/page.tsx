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
import PageHeader from "@/components/ui/PageHeader";
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
  const instrumentFacts = [
    {
      label: sizeLabel,
      value: isKr ? fmtJo(size) : formatMarketCap(size, meta.iso_code),
    },
    ...(!isKr && meta.shares_outstanding != null
      ? [{ label: "발행주식", value: formatShares(meta.shares_outstanding) }]
      : []),
    ...(isKr
      ? [
          {
            label: "거래대금",
            value: summary.value != null ? fmtJo(summary.value) : "—",
          },
          {
            label: "PER",
            value: summary.per != null ? summary.per.toFixed(2) : "—",
          },
          {
            label: "PBR",
            value: summary.pbr != null ? summary.pbr.toFixed(2) : "—",
          },
          {
            label: "배당수익률",
            value: summary.div != null ? `${summary.div.toFixed(2)}%` : "—",
          },
        ]
      : []),
  ];

  return (
    <div className="flex flex-col gap-6 pb-16">
      <div className="flex items-start gap-3 sm:gap-4">
        <button
          onClick={() => router.back()}
          aria-label="뒤로 가기"
          className="mt-1 shrink-0 rounded-xl border border-edge bg-raised p-2.5 text-ink-secondary transition-colors hover:bg-overlay hover:text-ink"
        >
          <ArrowLeft size={18} />
        </button>
        <div className="min-w-0 flex-1">
          <PageHeader
            eyebrow="Security dossier"
            title={meta.name ?? meta.ticker}
            description={
              <>
                <span className="num">{meta.ticker}</span>
                {meta.sector ? ` · ${meta.sector}` : ""}
                {` · ${referenceTypeLabel}`}
              </>
            }
            meta={
              <>
                <span>{meta.iso_code}</span>
                <span>·</span>
                <span>{seriesContract.label}</span>
                <span>·</span>
                <span>
                  {seriesContract.cash_distributions === "included"
                    ? "현금분배 포함"
                    : seriesContract.cash_distributions === "implicit_in_reference_price"
                      ? "분배락 기준가격 반영"
                      : "현금분배 제외"}
                </span>
              </>
            }
            actions={
              <div className="text-left sm:text-right">
                <p className="num text-3xl font-semibold tracking-[-0.04em] text-ink">
                  {formatPrice(summary.latest_price, meta.iso_code)}
                </p>
                <p className="mt-1 text-[11px] text-ink-muted num">
                  {summary.latest_date
                    ? `가격 기준 ${formatDate(summary.latest_date)}`
                    : "가격 기준일 없음"}
                </p>
              </div>
            }
          />

          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-edge pt-4 sm:pl-5">
            <WatchlistStar metaId={meta.meta_id} />
            <HoldingButton
              metaId={meta.meta_id}
              ticker={meta.ticker}
              name={meta.name}
              isoCode={meta.iso_code}
              holding={detail.holding}
            />
            {isEtf && (
              <span
                className="badge font-semibold"
                style={{
                  color: "var(--secondary)",
                  backgroundColor: "color-mix(in srgb, var(--secondary) 12%, transparent)",
                }}
              >
                {meta.security_subtype && meta.security_subtype !== "ETF"
                  ? `ETF · ${meta.security_subtype}`
                  : "ETF"}
              </span>
            )}
            <span className="mx-1 hidden h-4 w-px bg-edge sm:block" aria-hidden />
            {isKr && (
              <a
                href={`https://finance.naver.com/item/main.naver?code=${meta.ticker}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-secondary transition-colors hover:bg-raised hover:text-ink"
              >
                네이버 금융 <ExternalLink size={12} aria-hidden />
              </a>
            )}
            <a
              href={`https://www.tradingview.com/symbols/${tradingViewSymbol}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-ink-secondary transition-colors hover:bg-raised hover:text-ink"
            >
              TradingView <ExternalLink size={12} aria-hidden />
            </a>
          </div>
        </div>
      </div>

      <div
        className="scrollbar-hidden -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
        role="group"
        aria-label="수익과 위험 요약"
        tabIndex={0}
      >
        <section className="metric-strip min-w-[42rem] grid-cols-5 sm:min-w-0" aria-label="수익과 위험 요약">
          <StatTile label="3개월" value={fmtReturn(metrics.return_3m)} deltaType={returnDelta(metrics.return_3m)} />
          <StatTile label="연초 이후" value={fmtReturn(metrics.ytd_return)} deltaType={returnDelta(metrics.ytd_return)} />
          <StatTile label="1년" value={fmtReturn(metrics.return_1y)} deltaType={returnDelta(metrics.return_1y)} />
          <StatTile label="변동성" value={fmtReturn(metrics.volatility)} />
          <StatTile label="최대 낙폭" value={fmtReturn(metrics.mdd)} deltaType={metrics.mdd != null && metrics.mdd < 0 ? "loss" : "neutral"} />
        </section>
      </div>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_19rem]" aria-label="가격 근거와 종목 기준값">
        <Card
          className="min-w-0"
          headingLevel={2}
          title={isKr ? "가격 · 투자자 수급" : "가격 흐름"}
          action={
            <div className="flex flex-wrap items-center gap-2">
              {isKr && <Segmented options={FLOW_OPTIONS} value={flowMode} onChange={setFlowMode} />}
              <Segmented
                options={PERIOD_OPTIONS.map((option) => ({ id: option.value, label: option.label }))}
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
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-edge pb-3 text-xs">
                <span className="font-semibold text-ink">{seriesContract.label}</span>
                <span className="text-ink-muted num">{seriesContract.calculation_version}</span>
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

        <div className="overflow-hidden rounded-2xl border border-edge bg-surface">
          <div className="border-b border-edge px-5 py-4">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Instrument index</p>
            <h2 className="mt-1 text-base font-semibold text-ink">종목 기준값</h2>
          </div>
          <dl className="divide-y divide-edge px-5">
            {instrumentFacts.map((fact) => (
              <div key={fact.label} className="flex items-baseline justify-between gap-4 py-3">
                <dt className="text-xs text-ink-muted">{fact.label}</dt>
                <dd className="num text-sm font-semibold text-ink">{fact.value}</dd>
              </div>
            ))}
          </dl>
          <div className="border-t border-edge bg-raised/50 px-5 py-4 text-[11px] leading-5 text-ink-muted">
            {!isKr ? (
              <>
                <p className="font-semibold text-ink-secondary">
                  참조 데이터{meta.reference_as_of ? ` · ${formatDate(meta.reference_as_of)}` : " · 기준일 없음"}
                </p>
                <p className="mt-1">Type {referenceTypeLabel}</p>
                {meta.weighted_shares_outstanding != null && <p>Weighted shares {formatShares(meta.weighted_shares_outstanding)}</p>}
                {sizeSource && <p>Size source {formatReferenceSource(sizeSource)}</p>}
                {meta.fund_size_source === "estimate_close_x_share_class_shares" && (
                  <p className="mt-2">Fund Size는 최근 종가×발행좌수 추정치이며 운용사 보고 AUM이 아닙니다.{meta.fund_size_as_of ? ` 가격 기준 ${formatDate(meta.fund_size_as_of)}` : ""}</p>
                )}
                {meta.marketcap_source === "massive_close_x_weighted_shares" && (
                  <p className="mt-2">Market Cap은 최근 종가와 Massive 가중 발행주식수로 계산했습니다.{meta.marketcap_as_of ? ` 가격 기준 ${formatDate(meta.marketcap_as_of)}` : ""}</p>
                )}
              </>
            ) : isEtf || !summary.valuation ? (
              <p>가격·규모 기준값은 최신 레이크 스냅샷을 사용합니다.</p>
            ) : (
              <>
                <p className="font-semibold text-ink-secondary">
                  밸류에이션{summary.valuation.as_of ? ` · ${formatDate(summary.valuation.as_of)}` : " · 기준일 없음"}
                </p>
                <p className="mt-1 num">{summary.valuation.calculation_version}</p>
                <p className="mt-2">같은 날짜의 KRX 가격·시가총액·주식수와 EPS/BPS/DPS로 재계산해 원천값과 대조합니다.</p>
                {summary.valuation.missing_reasons.length > 0 && <p className="mt-2 text-warning">{summary.valuation.missing_reasons.join(" ")}</p>}
              </>
            )}
          </div>
        </div>
      </section>

      {!isKr && !isEtf && (
        <FundamentalsCard
          facts={fundamentalData?.facts}
          asOf={fundamentalData?.as_of}
          note={fundamentalData?.note}
          isLoading={fundamentalLoading}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* KR flow summary */}
        {isKr && flows && (
          <Card
            className="only:lg:col-span-2"
            title={
              <span className="inline-flex items-center gap-1.5">
                최근 수급 · 20거래일
                <InfoTip helpKey="signal.intensity" />
              </span>
            }
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <StatTile
                label="외국인 순매수"
                value={fmtEok(flows.frgn_net_20d)}
                deltaType={returnDelta(flows.frgn_net_20d)}
              />
              <StatTile
                label="기관 순매수"
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
              className="only:lg:col-span-2"
              title={
                <span className="inline-flex items-center gap-1.5">
                  팩터 노출
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
    </div>
  );
};

export default StockDetailPage;
