"use client";

import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  useFetchAlgorithmsQuery,
  useFetchTickersQuery,
  BacktestPayload,
  BacktestParams,
  RebalFreq,
  BenchmarkName,
  BacktestCurrency,
  useFetchPriceCoverageQuery,
} from "@/state/api";
import Select, { SingleValue, MultiValue } from "react-select";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {
  tokenSelectStyles,
  tokenSelectErrorStyles,
} from "@/components/ui/selectStyles";
import InfoTip from "@/components/ui/InfoTip";

interface TickerData {
  iso_code: string;
  security_type: string;
  meta_id: string;
  ticker: string;
}

interface AlgorithmData {
  strategy: string;
  strategy_name: string;
}

interface SelectOption {
  value: string;
  label: string;
}

interface ValidationErrors {
  strategyName?: string;
  tickers?: string;
  algorithm?: string;
  dates?: string;
  weights?: string;
  coverage?: string;
}

interface SetStrategyProps {
  onRunBacktest: (payload: BacktestPayload) => void;
  isLoading?: boolean;
}

const selectStyles = tokenSelectStyles;
const selectErrorStyles = tokenSelectErrorStyles;

const REBAL_OPTIONS: { value: RebalFreq; label: string }[] = [
  { value: "M", label: "매월" },
  { value: "Q", label: "분기" },
  { value: "Y", label: "연간" },
];

const BENCHMARK_OPTIONS: SelectOption[] = [
  { value: "SPY", label: "SPY" },
  { value: "KOSPI", label: "KOSPI" },
  { value: "KOSDAQ", label: "KOSDAQ" },
  { value: "60_40", label: "60/40" },
];

const CURRENCY_OPTIONS: BacktestCurrency[] = ["USD", "KRW"];

/** ?weights=SPY:0.6,IEF:0.4 → { SPY: 0.6, IEF: 0.4 } (null if absent/invalid) */
const parseWeightsParam = (raw: string | null): Record<string, number> | null => {
  if (!raw) return null;
  const out: Record<string, number> = {};
  for (const part of raw.split(",")) {
    const [ticker, w] = part.split(":");
    const weight = Number(w);
    if (!ticker || !Number.isFinite(weight)) return null;
    out[ticker.trim()] = weight;
  }
  return Object.keys(out).length > 0 ? out : null;
};

const SetStrategyInner: React.FC<SetStrategyProps> = ({
  onRunBacktest,
  isLoading = false,
}) => {
  const searchParams = useSearchParams();
  const { data } = useFetchTickersQuery({});
  const { data: algorithmData } = useFetchAlgorithmsQuery({});
  const [startDate, setStartDate] = useState(new Date("2010-01-01"));
  const [endDate, setEndDate] = useState(new Date());
  const [selectedIsoCode, setSelectedIsoCode] = useState<SelectOption | null>(
    null
  );
  const [selectedSecurityType, setSelectedSecurityType] =
    useState<SelectOption | null>(null);
  const [selectedTickers, setSelectedTickers] = useState<SelectOption[]>([]);
  const [selectedAlgorithm, setSelectedAlgorithm] =
    useState<SelectOption | null>(null);
  const [strategyName, setStrategyName] = useState("");
  const [errors, setErrors] = useState<ValidationErrors>({});

  // v2 controls
  const [rebalFreq, setRebalFreq] = useState<RebalFreq>("M");
  const [costBps, setCostBps] = useState(10);
  const [benchmark, setBenchmark] = useState<SelectOption>(BENCHMARK_OPTIONS[0]);
  const [currency, setCurrency] = useState<BacktestCurrency>("USD");
  const [topN, setTopN] = useState(4);
  const [lookbackMonths, setLookbackMonths] = useState(12);
  // Fixed weights coming from the optimization page (?weights=...)
  const [customWeights, setCustomWeights] = useState<Record<
    string,
    number
  > | null>(null);
  const selectedMetaIds = useMemo(
    () => selectedTickers.map((ticker) => Number(ticker.value)),
    [selectedTickers]
  );
  const { data: coverage, isFetching: isCoverageLoading } =
    useFetchPriceCoverageQuery(selectedMetaIds, {
      skip: selectedMetaIds.length === 0 || selectedMetaIds.length > 50,
    });

  // Apply URL params once, when the ticker universe is available
  const appliedParamsRef = useRef(false);
  useEffect(() => {
    if (appliedParamsRef.current || !data) return;

    const weightsParam = parseWeightsParam(searchParams.get("weights"));
    const metaIdsParam = searchParams.get("meta_ids");

    if (weightsParam) {
      appliedParamsRef.current = true;
      const tickerRows = (data as TickerData[]).filter((item) =>
        Object.prototype.hasOwnProperty.call(weightsParam, item.ticker)
      );
      // 티커 → meta_id 매핑 (중복 티커는 첫 항목 사용)
      const seen = new Set<string>();
      const options: SelectOption[] = [];
      for (const row of tickerRows) {
        if (seen.has(row.ticker)) continue;
        seen.add(row.ticker);
        options.push({ value: row.meta_id, label: row.ticker });
      }
      setSelectedTickers(options);
      setSelectedAlgorithm({ value: "custom", label: "Custom (fixed weights)" });
      setCustomWeights(weightsParam);
      return;
    }

    if (metaIdsParam) {
      appliedParamsRef.current = true;
      const wanted = new Set(
        metaIdsParam
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      );
      const options = (data as TickerData[])
        .filter((item) => wanted.has(String(item.meta_id)))
        .map((item) => ({ value: item.meta_id, label: item.ticker }));
      if (options.length > 0) setSelectedTickers(options);
    }
  }, [data, searchParams]);

  const isoCodeOptions = useMemo(
    () =>
      data
        ? Array.from(
            new Set(data.map((item: TickerData) => item.iso_code))
          ).map(
            (code) =>
              ({
                value: code,
                label: code,
              }) as SelectOption
          )
        : [],
    [data]
  );

  const securityTypeOptions = useMemo(
    () =>
      data
        ? Array.from(
            new Set(data.map((item: TickerData) => item.security_type))
          ).map(
            (type) =>
              ({
                value: type,
                label: type,
              }) as SelectOption
          )
        : [],
    [data]
  );

  const tickerOptions = useMemo(
    () =>
      data
        ? data
            .filter(
              (item: TickerData) =>
                (!selectedIsoCode || item.iso_code === selectedIsoCode.value) &&
                (!selectedSecurityType ||
                  item.security_type === selectedSecurityType.value)
            )
            .map((item: TickerData) => ({
              value: item.meta_id,
              label: item.ticker,
            }))
        : [],
    [data, selectedIsoCode, selectedSecurityType]
  );

  const algorithmOptions = useMemo(() => {
    const options: SelectOption[] = algorithmData
      ? algorithmData.map((alg: AlgorithmData) => ({
          value: alg.strategy,
          label: alg.strategy_name,
        }))
      : [];
    if (!options.some((opt) => opt.value === "momentum")) {
      options.push({ value: "momentum", label: "Momentum (custom)" });
    }
    return options;
  }, [algorithmData]);

  const isMomentum = selectedAlgorithm?.value === "momentum";
  const isCustom = selectedAlgorithm?.value === "custom";

  const handleIsoCodeChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedIsoCode(newValue);
  };

  const handleSecurityTypeChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedSecurityType(newValue);
  };

  const handleAlgorithmChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedAlgorithm(newValue);
    if (newValue?.value !== "custom") setCustomWeights(null);
  };

  const handleTickersChange = (newValue: MultiValue<SelectOption>) => {
    setSelectedTickers(newValue as SelectOption[]);
  };

  const validateForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    if (!strategyName.trim()) {
      newErrors.strategyName = "실험 이름을 입력해 주세요";
    }

    if (selectedTickers.length === 0) {
      newErrors.tickers = "자산을 1개 이상 선택해 주세요";
    } else if (selectedTickers.length > 50) {
      newErrors.tickers = "한 번에 최대 50개 자산까지 검증할 수 있습니다";
    }

    if (!selectedAlgorithm) {
      newErrors.algorithm = "전략 규칙을 선택해 주세요";
    }

    if (selectedAlgorithm?.value === "custom" && !customWeights) {
      newErrors.weights =
        "고정 비중 전략은 최적화 결과에서 이 화면을 열어야 합니다";
    }

    if (startDate >= endDate) {
      newErrors.dates = "시작일은 종료일보다 앞서야 합니다";
    }

    if (!coverage?.complete || !coverage.effective_start || !coverage.effective_end) {
      newErrors.coverage = "선택 자산 모두에 공통 가격 구간이 있어야 실행할 수 있습니다";
    } else {
      const requestedStart = startDate.toISOString().split("T")[0];
      const requestedEnd = endDate.toISOString().split("T")[0];
      if (
        requestedStart < coverage.effective_start ||
        requestedEnd > coverage.effective_end
      ) {
        newErrors.coverage = `요청 기간을 실제 공통 구간 ${coverage.effective_start} ~ ${coverage.effective_end} 안으로 맞춰주세요`;
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleButtonClick = () => {
    if (!validateForm()) return;

    let params: BacktestParams | undefined;
    if (isMomentum) {
      params = { top_n: topN, lookback_months: lookbackMonths };
    } else if (isCustom && customWeights) {
      params = { weights: customWeights };
    }

    const payload: BacktestPayload = {
      strategy_name: strategyName,
      meta_id: selectedTickers.map((opt) => Number(opt.value)),
      algorithm: selectedAlgorithm?.value,
      startDate: startDate.toISOString().split("T")[0],
      endDate: endDate.toISOString().split("T")[0],
      rebal_freq: rebalFreq,
      cost_bps: costBps,
      benchmark: benchmark.value as BenchmarkName,
      currency,
      params,
    };
    onRunBacktest(payload);
  };

  const applyCoverageDates = () => {
    if (!coverage?.effective_start || !coverage.effective_end) return;
    setStartDate(new Date(`${coverage.effective_start}T12:00:00`));
    setEndDate(new Date(`${coverage.effective_end}T12:00:00`));
    setErrors((previous) => ({
      ...previous,
      dates: undefined,
      coverage: undefined,
    }));
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_18px_60px_rgba(0,0,0,0.14)]">
      <div aria-hidden className="h-px bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" />
      <header className="flex flex-col gap-3 border-b border-edge px-5 py-5 sm:flex-row sm:items-start sm:justify-between md:px-6">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Experiment protocol</p>
          <h2 className="mt-1 text-lg font-semibold tracking-[-0.02em] text-ink">백테스트 가정표</h2>
          <p className="mt-1 text-sm text-ink-muted">결과를 보기 전에 가설·대상·체결 조건을 먼저 고정합니다.</p>
        </div>
        <span className="rounded-lg border border-edge bg-raised/60 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
          Research only · 01—04
        </span>
      </header>

      <div className="divide-y divide-edge">
        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="backtest-hypothesis">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">01</p>
            <h3 id="backtest-hypothesis" className="mt-1 text-sm font-semibold text-ink">가설과 규칙</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">실험을 식별하고 매매 규칙을 선택합니다.</p>
          </div>
          <div className="min-w-0 space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="input-label" htmlFor="strategy-name">실험 이름 <span className="text-danger">*</span></label>
                <input
                  id="strategy-name"
                  type="text"
                  value={strategyName}
                  placeholder="예: 글로벌 모멘텀 · 비용 10bp"
                  className={errors.strategyName ? "input-error" : "input"}
                  onChange={(event) => {
                    setStrategyName(event.target.value);
                    if (errors.strategyName) setErrors((previous) => ({ ...previous, strategyName: undefined }));
                  }}
                />
                {errors.strategyName && <p className="mt-1 text-xs text-danger">{errors.strategyName}</p>}
              </div>
              <div>
                <label className="input-label" htmlFor="strategy-algorithm">전략 규칙 <span className="text-danger">*</span></label>
                <Select<SelectOption>
                  inputId="strategy-algorithm"
                  placeholder="규칙 선택"
                  options={algorithmOptions}
                  value={selectedAlgorithm}
                  onChange={(newValue) => {
                    handleAlgorithmChange(newValue);
                    if (errors.algorithm || errors.weights) {
                      setErrors((previous) => ({ ...previous, algorithm: undefined, weights: undefined }));
                    }
                  }}
                  styles={errors.algorithm ? selectErrorStyles : selectStyles}
                />
                {errors.algorithm && <p className="mt-1 text-xs text-danger">{errors.algorithm}</p>}
                {errors.weights && <p className="mt-1 text-xs text-danger">{errors.weights}</p>}
              </div>
            </div>

            {isMomentum && (
              <div className="grid gap-4 border-t border-edge pt-4 md:grid-cols-2">
                <div>
                  <label className="input-label" htmlFor="strategy-top-n">선택 종목 수 (Top N)</label>
                  <input
                    id="strategy-top-n"
                    type="number"
                    min={1}
                    max={20}
                    value={topN}
                    className="input"
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      if (Number.isFinite(value)) setTopN(Math.max(1, Math.min(20, Math.round(value))));
                    }}
                  />
                </div>
                <div>
                  <label className="input-label" htmlFor="strategy-lookback">모멘텀 관찰 구간 (개월)</label>
                  <input
                    id="strategy-lookback"
                    type="number"
                    min={3}
                    max={36}
                    value={lookbackMonths}
                    className="input"
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      if (Number.isFinite(value)) setLookbackMonths(Math.max(3, Math.min(36, Math.round(value))));
                    }}
                  />
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="backtest-universe">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">02</p>
            <h3 id="backtest-universe" className="mt-1 text-sm font-semibold text-ink">투자 유니버스</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">필터는 검색을 돕고, 선택 자산이 실제 입력입니다.</p>
          </div>
          <div className="min-w-0 space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className="input-label" htmlFor="strategy-country">국가</label>
                <Select<SelectOption>
                  inputId="strategy-country"
                  options={isoCodeOptions}
                  placeholder="전체"
                  onChange={handleIsoCodeChange}
                  isClearable
                  styles={selectStyles}
                />
              </div>
              <div>
                <label className="input-label" htmlFor="strategy-security-type">자산 유형</label>
                <Select<SelectOption>
                  inputId="strategy-security-type"
                  options={securityTypeOptions}
                  placeholder="전체"
                  onChange={handleSecurityTypeChange}
                  isClearable
                  styles={selectStyles}
                />
              </div>
              <div>
                <label className="input-label" htmlFor="strategy-tickers">자산 <span className="text-danger">*</span></label>
                <Select<SelectOption, true>
                  inputId="strategy-tickers"
                  closeMenuOnSelect={false}
                  isMulti
                  options={tickerOptions}
                  value={selectedTickers}
                  placeholder="자산 선택"
                  onChange={(newValue) => {
                    handleTickersChange(newValue);
                    if (errors.tickers) setErrors((previous) => ({ ...previous, tickers: undefined }));
                  }}
                  styles={errors.tickers ? selectErrorStyles : selectStyles}
                />
                {errors.tickers && <p className="mt-1 text-xs text-danger">{errors.tickers}</p>}
              </div>
            </div>

            <div className="flex min-h-11 flex-wrap items-center gap-2 border-t border-edge pt-3 text-xs">
              <span className="font-mono text-ink-muted">UNIVERSE / {selectedTickers.length}</span>
              {selectedTickers.length > 0 ? (
                selectedTickers.map((ticker) => (
                  <span key={ticker.value} className="rounded-full border border-edge bg-raised px-2.5 py-1 font-mono text-ink-secondary">
                    {ticker.label}
                  </span>
                ))
              ) : (
                <span className="text-ink-muted">선택한 자산이 여기에 기록됩니다.</span>
              )}
            </div>

            {isCustom && customWeights && (
              <div className="border-t border-edge pt-4">
                <p className="input-label">최적화에서 전달된 고정 비중</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(customWeights).map(([ticker, weight]) => (
                    <span key={ticker} className="inline-flex items-center gap-1.5 rounded-full border border-primary-400/20 bg-primary-500/10 px-3 py-1.5 text-xs font-medium text-ink-secondary">
                      {ticker}<span className="num text-ink">{(weight * 100).toFixed(1)}%</span>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="backtest-execution">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">03</p>
            <h3 id="backtest-execution" className="mt-1 text-sm font-semibold text-ink">체결 조건</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">비용·기준·검증 구간을 명시합니다.</p>
          </div>
          <div className="min-w-0 space-y-5">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <p className="input-label">리밸런싱</p>
                <div className="inline-flex min-h-11 w-full rounded-xl border border-edge bg-raised p-1" aria-label="리밸런싱 주기">
                  {REBAL_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setRebalFreq(option.value)}
                      aria-pressed={rebalFreq === option.value}
                      className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${rebalFreq === option.value ? "bg-primary-500 text-white shadow-lg shadow-primary-500/20" : "text-ink-muted hover:text-ink"}`}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="input-label flex items-center gap-1" htmlFor="strategy-cost">
                  <span>거래비용 (bps)</span><InfoTip helpKey="bt.cost" />
                </label>
                <input
                  id="strategy-cost"
                  type="number"
                  min={0}
                  value={costBps}
                  className="input"
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (Number.isFinite(value)) setCostBps(Math.max(0, value));
                  }}
                />
              </div>
              <div>
                <label className="input-label" htmlFor="strategy-benchmark">벤치마크</label>
                <Select<SelectOption>
                  inputId="strategy-benchmark"
                  options={BENCHMARK_OPTIONS}
                  value={benchmark}
                  onChange={(newValue) => { if (newValue) setBenchmark(newValue); }}
                  styles={selectStyles}
                />
              </div>
              <div>
                <p className="input-label">기준 통화</p>
                <div className="inline-flex min-h-11 w-full rounded-xl border border-edge bg-raised p-1" aria-label="기준 통화">
                  {CURRENCY_OPTIONS.map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setCurrency(option)}
                      aria-pressed={currency === option}
                      className={`flex-1 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors ${currency === option ? "bg-primary-500 text-white shadow-lg shadow-primary-500/20" : "text-ink-muted hover:text-ink"}`}
                    >
                      {option}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid gap-4 border-t border-edge pt-5 md:grid-cols-2">
              <div>
                <label className="input-label" htmlFor="strategy-start-date">시작일</label>
                <DatePicker
                  id="strategy-start-date"
                  selected={startDate}
                  onChange={(date: Date | null) => {
                    setStartDate(date || new Date());
                    if (errors.dates) setErrors((previous) => ({ ...previous, dates: undefined }));
                  }}
                  placeholderText="시작일 선택"
                  className={errors.dates ? "input-error" : "input"}
                  wrapperClassName="w-full"
                />
              </div>
              <div>
                <label className="input-label" htmlFor="strategy-end-date">종료일</label>
                <DatePicker
                  id="strategy-end-date"
                  selected={endDate}
                  onChange={(date: Date | null) => {
                    setEndDate(date || new Date());
                    if (errors.dates) setErrors((previous) => ({ ...previous, dates: undefined }));
                  }}
                  placeholderText="종료일 선택"
                  className={errors.dates ? "input-error" : "input"}
                  wrapperClassName="w-full"
                />
              </div>
            </div>
            {errors.dates && <p className="text-xs text-danger">{errors.dates}</p>}

            {selectedTickers.length > 0 && (
              <div className="rounded-xl border border-edge bg-raised/60 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-ink">실제 공통 가격 구간</p>
                    {isCoverageLoading ? (
                      <p className="mt-1 text-xs text-ink-muted">가격 구간 확인 중…</p>
                    ) : coverage?.complete ? (
                      <p className="mt-1 text-xs text-ink-secondary">{coverage.effective_start} ~ {coverage.effective_end} · 조정주가</p>
                    ) : (
                      <p className="mt-1 text-xs text-danger">가격이 없는 자산이 있어 공통 구간을 만들 수 없습니다.</p>
                    )}
                    {coverage?.assets.some((asset) => asset.rows === 0) && (
                      <p className="mt-1 text-xs text-danger">
                        누락: {coverage.assets.filter((asset) => asset.rows === 0).map((asset) => asset.ticker ?? asset.meta_id).join(", ")}
                      </p>
                    )}
                    <p className="mt-2 text-[11px] leading-5 text-ink-muted">{coverage?.note ?? "종목을 선택하면 실제 저장 데이터의 교집합을 확인합니다."}</p>
                  </div>
                  <button type="button" className="btn-secondary shrink-0" onClick={applyCoverageDates} disabled={!coverage?.complete}>
                    공통 구간 적용
                  </button>
                </div>
                {errors.coverage && <p className="mt-2 text-xs text-danger">{errors.coverage}</p>}
              </div>
            )}
          </div>
        </section>

        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="backtest-review">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">04</p>
            <h3 id="backtest-review" className="mt-1 text-sm font-semibold text-ink">실행 확인</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">연구 한계를 확인한 뒤 실행합니다.</p>
          </div>
          <div className="min-w-0 space-y-4">
            <dl className="grid grid-cols-3 divide-x divide-edge border-y border-edge">
              <div className="px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wide text-ink-muted">자산</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-ink">{selectedTickers.length}개</dd>
              </div>
              <div className="px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wide text-ink-muted">리밸런싱</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-ink">{REBAL_OPTIONS.find((option) => option.value === rebalFreq)?.label}</dd>
              </div>
              <div className="px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wide text-ink-muted">거래비용</dt>
                <dd className="mt-1 font-mono text-sm font-semibold text-ink">{costBps} bp</dd>
              </div>
            </dl>
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
              <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 text-xs leading-5 text-ink-secondary">
                <p className="font-semibold text-ink">Research Lab · 연구용 미검증 결과</p>
                <p className="mt-1">
                  종목 선정 시점·상장폐지 포함 여부와 데이터 누출 감사를 통과한 결과가 아닙니다.
                  체결 비용을 입력했더라도 실전 배분 근거로 바로 사용하지 마세요.
                </p>
              </div>
              <button
                type="button"
                className="btn-primary min-h-11 whitespace-nowrap lg:min-w-40"
                onClick={handleButtonClick}
                disabled={isLoading || isCoverageLoading}
              >
                {isLoading ? "실행 중..." : "백테스트 실행"}
              </button>
            </div>
          </div>
        </section>
      </div>
    </section>
  );
};

// useSearchParams는 Suspense 경계 안에서만 프리렌더 가능
const SetStrategy: React.FC<SetStrategyProps> = (props) => (
  <Suspense fallback={<div className="card min-h-[200px]" />}>
    <SetStrategyInner {...props} />
  </Suspense>
);

export default SetStrategy;
