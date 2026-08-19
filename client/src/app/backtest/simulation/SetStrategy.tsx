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
  { value: "M", label: "Monthly" },
  { value: "Q", label: "Quarterly" },
  { value: "Y", label: "Yearly" },
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
      newErrors.strategyName = "Strategy name is required";
    }

    if (selectedTickers.length === 0) {
      newErrors.tickers = "Please select at least one ticker";
    } else if (selectedTickers.length > 50) {
      newErrors.tickers = "한 번에 최대 50개 자산까지 검증할 수 있습니다";
    }

    if (!selectedAlgorithm) {
      newErrors.algorithm = "Please select an algorithm";
    }

    if (selectedAlgorithm?.value === "custom" && !customWeights) {
      newErrors.weights =
        "Custom algorithm needs fixed weights — open this page from the Optimization results";
    }

    if (startDate >= endDate) {
      newErrors.dates = "Start date must be before end date";
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
    <div className="card">
      <h3 className="text-base font-semibold text-ink mb-6">
        Strategy Configuration
      </h3>

      <div className="space-y-5">
        {/* Strategy Name */}
        <div>
          <label className="input-label">
            Strategy Name <span className="text-danger">*</span>
          </label>
          <input
            type="text"
            placeholder="Enter your strategy name..."
            className={errors.strategyName ? "input-error" : "input"}
            onChange={(e) => {
              setStrategyName(e.target.value);
              if (errors.strategyName)
                setErrors((prev) => ({ ...prev, strategyName: undefined }));
            }}
          />
          {errors.strategyName && (
            <p className="text-danger text-xs mt-1">{errors.strategyName}</p>
          )}
        </div>

        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="input-label">Country</label>
            <Select<SelectOption>
              options={isoCodeOptions}
              placeholder="Select..."
              onChange={handleIsoCodeChange}
              isClearable
              styles={selectStyles}
            />
          </div>
          <div>
            <label className="input-label">Security Type</label>
            <Select<SelectOption>
              options={securityTypeOptions}
              placeholder="Select..."
              onChange={handleSecurityTypeChange}
              isClearable
              styles={selectStyles}
            />
          </div>
          <div>
            <label className="input-label">
              Tickers <span className="text-danger">*</span>
            </label>
            <Select<SelectOption, true>
              closeMenuOnSelect={false}
              isMulti
              options={tickerOptions}
              value={selectedTickers}
              placeholder="Select tickers..."
              onChange={(newValue) => {
                handleTickersChange(newValue);
                if (errors.tickers)
                  setErrors((prev) => ({ ...prev, tickers: undefined }));
              }}
              styles={errors.tickers ? selectErrorStyles : selectStyles}
            />
            {errors.tickers && (
              <p className="text-danger text-xs mt-1">{errors.tickers}</p>
            )}
          </div>
        </div>

        {/* Algorithm */}
        <div>
          <label className="input-label">
            Algorithm <span className="text-danger">*</span>
          </label>
          <Select<SelectOption>
            placeholder="Select algorithm..."
            options={algorithmOptions}
            value={selectedAlgorithm}
            onChange={(newValue) => {
              handleAlgorithmChange(newValue);
              if (errors.algorithm || errors.weights)
                setErrors((prev) => ({
                  ...prev,
                  algorithm: undefined,
                  weights: undefined,
                }));
            }}
            styles={errors.algorithm ? selectErrorStyles : selectStyles}
          />
          {errors.algorithm && (
            <p className="text-danger text-xs mt-1">{errors.algorithm}</p>
          )}
          {errors.weights && (
            <p className="text-danger text-xs mt-1">{errors.weights}</p>
          )}
        </div>

        {/* Fixed weights summary (from Optimization page) */}
        {isCustom && customWeights && (
          <div>
            <label className="input-label">Fixed Weights</label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(customWeights).map(([ticker, weight]) => (
                <span
                  key={ticker}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-raised text-xs font-medium text-ink-secondary"
                >
                  {ticker}
                  <span className="num text-ink">
                    {(weight * 100).toFixed(1)}%
                  </span>
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Momentum params */}
        {isMomentum && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="input-label">Top N</label>
              <input
                type="number"
                min={1}
                max={20}
                value={topN}
                className="input"
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v))
                    setTopN(Math.max(1, Math.min(20, Math.round(v))));
                }}
              />
            </div>
            <div>
              <label className="input-label">Lookback (months)</label>
              <input
                type="number"
                min={3}
                max={36}
                value={lookbackMonths}
                className="input"
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (Number.isFinite(v))
                    setLookbackMonths(Math.max(3, Math.min(36, Math.round(v))));
                }}
              />
            </div>
          </div>
        )}

        {/* Rebalance / Cost / Benchmark / Currency */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="input-label">Rebalance</label>
            <div className="inline-flex w-full rounded-lg bg-raised p-1">
              {REBAL_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setRebalFreq(opt.value)}
                  className={`flex-1 px-2 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    rebalFreq === opt.value
                      ? "bg-surface text-ink shadow-sm"
                      : "text-ink-muted hover:text-ink-secondary"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="input-label flex items-center gap-1">
              <span>Cost (bps)</span>
              <InfoTip helpKey="bt.cost" />
            </label>
            <input
              type="number"
              min={0}
              value={costBps}
              className="input"
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v)) setCostBps(Math.max(0, v));
              }}
            />
          </div>
          <div>
            <label className="input-label">Benchmark</label>
            <Select<SelectOption>
              options={BENCHMARK_OPTIONS}
              value={benchmark}
              onChange={(newValue) => {
                if (newValue) setBenchmark(newValue);
              }}
              styles={selectStyles}
            />
          </div>
          <div>
            <label className="input-label">Currency</label>
            <div className="inline-flex w-full rounded-lg bg-raised p-1">
              {CURRENCY_OPTIONS.map((cur) => (
                <button
                  key={cur}
                  type="button"
                  onClick={() => setCurrency(cur)}
                  className={`flex-1 px-2 py-1.5 text-xs font-medium rounded-md transition-colors ${
                    currency === cur
                      ? "bg-surface text-ink shadow-sm"
                      : "text-ink-muted hover:text-ink-secondary"
                  }`}
                >
                  {cur}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="input-label">Start Date</label>
            <DatePicker
              selected={startDate}
              onChange={(date: Date | null) => {
                setStartDate(date || new Date());
                if (errors.dates)
                  setErrors((prev) => ({ ...prev, dates: undefined }));
              }}
              placeholderText="Select start date"
              className={errors.dates ? "input-error" : "input"}
            />
          </div>
          <div>
            <label className="input-label">End Date</label>
            <DatePicker
              selected={endDate}
              onChange={(date: Date | null) => {
                setEndDate(date || new Date());
                if (errors.dates)
                  setErrors((prev) => ({ ...prev, dates: undefined }));
              }}
              placeholderText="Select end date"
              className={errors.dates ? "input-error" : "input"}
            />
          </div>
        </div>
        {errors.dates && (
          <p className="text-danger text-xs">{errors.dates}</p>
        )}

        {selectedTickers.length > 0 && (
          <div className="rounded-xl border border-edge bg-raised/60 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-ink">실제 데이터 구간</p>
                {isCoverageLoading ? (
                  <p className="mt-1 text-xs text-ink-muted">가격 구간 확인 중…</p>
                ) : coverage?.complete ? (
                  <p className="mt-1 text-xs text-ink-secondary">
                    공통 {coverage.effective_start} ~ {coverage.effective_end} · 조정주가
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-danger">
                    가격이 없는 자산이 있어 공통 구간을 만들 수 없습니다.
                  </p>
                )}
                {coverage?.assets.some((asset) => asset.rows === 0) && (
                  <p className="mt-1 text-xs text-danger">
                    누락: {coverage.assets
                      .filter((asset) => asset.rows === 0)
                      .map((asset) => asset.ticker ?? asset.meta_id)
                      .join(", ")}
                  </p>
                )}
                <p className="mt-2 text-[11px] leading-5 text-ink-muted">
                  {coverage?.note ?? "종목을 선택하면 실제 저장 데이터의 교집합을 확인합니다."}
                </p>
              </div>
              <button
                type="button"
                className="btn-secondary shrink-0"
                onClick={applyCoverageDates}
                disabled={!coverage?.complete}
              >
                공통 구간 적용
              </button>
            </div>
            {errors.coverage && (
              <p className="mt-2 text-xs text-danger">{errors.coverage}</p>
            )}
          </div>
        )}

        <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 text-xs leading-5 text-ink-secondary">
          <p className="font-semibold text-ink">Research Lab · 연구용 미검증 결과</p>
          <p className="mt-1">
            실제 공통 가격 구간, 조정주가, 거래비용, 기준통화와 벤치마크를 명시합니다.
            종목 선정 시점·상장폐지 포함 여부와 데이터 누출 감사까지 통과한 결과는 아니므로
            실전 배분 근거로 바로 사용하지 마세요.
          </p>
        </div>

        {/* Run Button */}
        <div className="flex justify-end pt-2">
          <button
            className="btn-primary"
            onClick={handleButtonClick}
            disabled={isLoading || isCoverageLoading}
          >
            {isLoading ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </div>
    </div>
  );
};

// useSearchParams는 Suspense 경계 안에서만 프리렌더 가능
const SetStrategy: React.FC<SetStrategyProps> = (props) => (
  <Suspense fallback={<div className="card min-h-[200px]" />}>
    <SetStrategyInner {...props} />
  </Suspense>
);

export default SetStrategy;
