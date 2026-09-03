"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useFetchTickersQuery, OptimizationPayload } from "@/state/api";
import Select, { SingleValue, MultiValue } from "react-select";
import { tokenSelectStyles } from "@/components/ui/selectStyles";

interface TickerData {
  iso_code: string;
  security_type: string;
  meta_id: number;
  ticker: string;
}

interface SelectOption {
  value: number | string;
  label: string;
}

interface ValidationErrors {
  tickers?: string;
  lookback?: string;
  weights?: string;
}

export type OptimizationConfigType = "mvo" | "risk_parity" | "correlation";

interface OptimizationConfigProps {
  onOptimize: (payload: OptimizationPayload) => void;
  isLoading?: boolean;
  optimizationType: OptimizationConfigType;
}

const TYPE_TITLES: Record<OptimizationConfigType, string> = {
  mvo: "평균-분산 가정",
  risk_parity: "리스크 패리티 가정",
  correlation: "상관관계 가정",
};

const TYPE_DESCRIPTIONS: Record<OptimizationConfigType, string> = {
  mvo: "과거 수익률과 공분산으로 효율적 투자선을 계산합니다.",
  risk_parity: "예측 수익률보다 각 자산의 위험 기여를 균등하게 맞춥니다.",
  correlation: "선택 자산의 정적·롤링 상관 구조를 확인합니다.",
};

const selectStyles = tokenSelectStyles;

const OptimizationConfig: React.FC<OptimizationConfigProps> = ({
  onOptimize,
  isLoading = false,
  optimizationType,
}) => {
  const { data: tickerData } = useFetchTickersQuery({});

  const [selectedIsoCode, setSelectedIsoCode] = useState<SelectOption | null>(null);
  const [selectedTickers, setSelectedTickers] = useState<SelectOption[]>([]);
  const [lookbackPeriod, setLookbackPeriod] = useState(252);
  const [riskFreeRate, setRiskFreeRate] = useState(0);
  const [minWeight, setMinWeight] = useState(0);
  const [maxWeight, setMaxWeight] = useState(0.25);
  const [errors, setErrors] = useState<ValidationErrors>({});

  const isoCodeOptions = useMemo(
    () =>
      tickerData
        ? Array.from(new Set(tickerData.map((item: TickerData) => item.iso_code))).map(
            (code) => ({ value: code, label: code }) as SelectOption
          )
        : [],
    [tickerData]
  );

  const tickerOptions = useMemo(
    () =>
      tickerData
        ? tickerData
            .filter(
              (item: TickerData) =>
                !selectedIsoCode || item.iso_code === selectedIsoCode.value
            )
            .map((item: TickerData) => ({
              value: item.meta_id,
              label: item.ticker,
            }))
        : [],
    [tickerData, selectedIsoCode]
  );

  useEffect(() => {
    if (selectedTickers.length > 0) {
      setMaxWeight(Math.max(0.25, 1 / selectedTickers.length));
    }
  }, [selectedTickers.length]);

  const validateForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    if (selectedTickers.length < 2) {
      newErrors.tickers = "자산을 2개 이상 선택해 주세요";
    }

    if (lookbackPeriod < 60 || lookbackPeriod > 1260) {
      newErrors.lookback = "추정 구간은 60~1,260일 사이여야 합니다";
    }

    if (minWeight >= maxWeight) {
      newErrors.weights = "최소 비중은 최대 비중보다 작아야 합니다";
    } else if (selectedTickers.length > 0 && minWeight * selectedTickers.length > 1) {
      newErrors.weights = "최소 비중의 합이 100%를 초과해 해가 존재하지 않습니다";
    } else if (selectedTickers.length > 0 && maxWeight * selectedTickers.length < 1) {
      newErrors.weights = "최대 비중으로 100%를 채울 수 없어 해가 존재하지 않습니다";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleOptimize = () => {
    if (!validateForm()) return;

    const payload: OptimizationPayload = {
      meta_id: selectedTickers.map((t) => t.value as number),
      lookback_period: lookbackPeriod,
      risk_free_rate: riskFreeRate,
      min_weight: minWeight,
      max_weight: maxWeight,
      n_points: 50,
    };

    onOptimize(payload);
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_18px_60px_rgba(0,0,0,0.14)]">
      <div aria-hidden className="h-px bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" />
      <header className="flex flex-col gap-3 border-b border-edge px-5 py-5 sm:flex-row sm:items-start sm:justify-between md:px-6">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">
            Assumption sheet
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-[-0.02em] text-ink">
            {TYPE_TITLES[optimizationType]}
          </h2>
          <p className="mt-1 text-sm text-ink-muted">{TYPE_DESCRIPTIONS[optimizationType]}</p>
        </div>
        <div className="rounded-lg border border-edge bg-raised/60 px-3 py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
          입력 → 계산 → 검토
        </div>
      </header>

      <div className="divide-y divide-edge">
        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="optimization-universe">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">01</p>
            <h3 id="optimization-universe" className="mt-1 text-sm font-semibold text-ink">자산 범위</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">비교할 시장과 자산 집합을 고릅니다.</p>
          </div>
          <div className="min-w-0 space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="input-label" htmlFor="optimization-country">국가</label>
                <Select<SelectOption>
                  inputId="optimization-country"
                  options={isoCodeOptions}
                  placeholder="전체 국가"
                  onChange={(value: SingleValue<SelectOption>) => setSelectedIsoCode(value)}
                  isClearable
                  styles={selectStyles}
                />
              </div>
              <div>
                <label className="input-label" htmlFor="optimization-assets">
                  자산 <span className="text-danger">*</span>
                </label>
                <Select<SelectOption, true>
                  inputId="optimization-assets"
                  closeMenuOnSelect={false}
                  isMulti
                  options={tickerOptions}
                  placeholder="자산을 2개 이상 선택"
                  value={selectedTickers}
                  onChange={(value: MultiValue<SelectOption>) => {
                    setSelectedTickers(value as SelectOption[]);
                    if (errors.tickers) setErrors((previous) => ({ ...previous, tickers: undefined }));
                  }}
                  styles={selectStyles}
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
          </div>
        </section>

        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="optimization-estimation">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">02</p>
            <h3 id="optimization-estimation" className="mt-1 text-sm font-semibold text-ink">추정 조건</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">표본 구간과 허용 비중을 명시합니다.</p>
          </div>
          <div className="min-w-0">
            <div className={`grid grid-cols-1 gap-4 ${optimizationType === "mvo" ? "md:grid-cols-2 xl:grid-cols-4" : optimizationType === "correlation" ? "max-w-sm" : "md:grid-cols-2"}`}>
              <div>
                <label className="input-label" htmlFor="optimization-lookback">추정 구간 (거래일)</label>
                <input
                  id="optimization-lookback"
                  type="number"
                  value={lookbackPeriod}
                  onChange={(event) => setLookbackPeriod(parseInt(event.target.value) || 252)}
                  className="input"
                  min={60}
                  max={1260}
                />
                {errors.lookback && <p className="mt-1 text-xs text-danger">{errors.lookback}</p>}
              </div>
              {optimizationType !== "correlation" && (
                <div>
                  <label className="input-label" htmlFor="optimization-risk-free">무위험수익률 (%)</label>
                  <input
                    id="optimization-risk-free"
                    type="number"
                    value={riskFreeRate * 100}
                    onChange={(event) => setRiskFreeRate(parseFloat(event.target.value) / 100 || 0)}
                    className="input"
                    step={0.1}
                    min={0}
                    max={20}
                  />
                </div>
              )}
              {optimizationType === "mvo" && (
                <>
                  <div>
                    <label className="input-label" htmlFor="optimization-min-weight">최소 비중 (%)</label>
                    <input
                      id="optimization-min-weight"
                      type="number"
                      value={minWeight * 100}
                      onChange={(event) => setMinWeight(parseFloat(event.target.value) / 100 || 0)}
                      className="input"
                      step={1}
                      min={0}
                      max={100}
                    />
                  </div>
                  <div>
                    <label className="input-label" htmlFor="optimization-max-weight">최대 비중 (%)</label>
                    <input
                      id="optimization-max-weight"
                      type="number"
                      value={maxWeight * 100}
                      onChange={(event) => setMaxWeight(parseFloat(event.target.value) / 100 || 1)}
                      className="input"
                      step={1}
                      min={0}
                      max={100}
                    />
                  </div>
                </>
              )}
            </div>
            {errors.weights && <p className="mt-2 text-xs text-danger">{errors.weights}</p>}
          </div>
        </section>

        <section className="grid gap-5 px-5 py-6 md:grid-cols-[8rem_minmax(0,1fr)] md:px-6" aria-labelledby="optimization-run">
          <div>
            <p className="font-mono text-xs font-semibold text-primary-300">03</p>
            <h3 id="optimization-run" className="mt-1 text-sm font-semibold text-ink">실행 확인</h3>
            <p className="mt-1 text-xs leading-5 text-ink-muted">계산 전에 결과의 한계를 확인합니다.</p>
          </div>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div className="rounded-xl border border-warning/30 bg-warning/5 p-4 text-xs leading-5 text-ink-secondary">
              <p className="font-semibold text-ink">Research Lab · 추정 오차 주의</p>
              <p className="mt-1">
                과거 표본 안에서만 추정하며 표본 외 검증·회전율·세금·거래비용은 포함하지 않습니다.
                계산 결과를 그대로 실전 비중으로 사용하지 마세요.
              </p>
            </div>
            <button
              type="button"
              className="btn-primary min-h-11 whitespace-nowrap lg:min-w-36"
              onClick={handleOptimize}
              disabled={isLoading || selectedTickers.length < 2}
            >
              {isLoading
                ? "계산 중..."
                : optimizationType === "correlation"
                  ? "분석 실행"
                  : "최적화 실행"}
            </button>
          </div>
        </section>
      </div>
    </section>
  );
};

export default OptimizationConfig;
