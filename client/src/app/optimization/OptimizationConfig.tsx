"use client";

import React, { useMemo, useState } from "react";
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
  mvo: "Mean-Variance Optimization",
  risk_parity: "Risk Parity Optimization",
  correlation: "Correlation Analysis",
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
  const [riskFreeRate, setRiskFreeRate] = useState(0.02);
  const [minWeight, setMinWeight] = useState(0);
  const [maxWeight, setMaxWeight] = useState(1);
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

  const validateForm = (): boolean => {
    const newErrors: ValidationErrors = {};

    if (selectedTickers.length < 2) {
      newErrors.tickers = "Please select at least 2 assets";
    }

    if (lookbackPeriod < 60 || lookbackPeriod > 1260) {
      newErrors.lookback = "Lookback period must be between 60 and 1260 days";
    }

    if (minWeight >= maxWeight) {
      newErrors.weights = "Min weight must be less than max weight";
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
    <div className="card">
      <h3 className="text-base font-semibold text-ink mb-6">
        {TYPE_TITLES[optimizationType]}
      </h3>

      <div className="space-y-5">
        {/* Country Filter */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="input-label">Country</label>
            <Select<SelectOption>
              options={isoCodeOptions}
              placeholder="All countries..."
              onChange={(val: SingleValue<SelectOption>) => setSelectedIsoCode(val)}
              isClearable
              styles={selectStyles}
            />
          </div>
          <div>
            <label className="input-label">
              Assets <span className="text-danger">*</span>
            </label>
            <Select<SelectOption, true>
              closeMenuOnSelect={false}
              isMulti
              options={tickerOptions}
              placeholder="Select at least 2 assets..."
              value={selectedTickers}
              onChange={(val: MultiValue<SelectOption>) => {
                setSelectedTickers(val as SelectOption[]);
                if (errors.tickers) setErrors((prev) => ({ ...prev, tickers: undefined }));
              }}
              styles={selectStyles}
            />
            {errors.tickers && (
              <p className="text-danger text-xs mt-1">{errors.tickers}</p>
            )}
          </div>
        </div>

        {/* Parameters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="input-label">Lookback (days)</label>
            <input
              type="number"
              value={lookbackPeriod}
              onChange={(e) => setLookbackPeriod(parseInt(e.target.value) || 252)}
              className="input"
              min={60}
              max={1260}
            />
            {errors.lookback && (
              <p className="text-danger text-xs mt-1">{errors.lookback}</p>
            )}
          </div>
          {optimizationType !== "correlation" && (
            <div>
              <label className="input-label">Risk-Free Rate (%)</label>
              <input
                type="number"
                value={riskFreeRate * 100}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) / 100 || 0)}
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
                <label className="input-label">Min Weight (%)</label>
                <input
                  type="number"
                  value={minWeight * 100}
                  onChange={(e) => setMinWeight(parseFloat(e.target.value) / 100 || 0)}
                  className="input"
                  step={1}
                  min={0}
                  max={100}
                />
              </div>
              <div>
                <label className="input-label">Max Weight (%)</label>
                <input
                  type="number"
                  value={maxWeight * 100}
                  onChange={(e) => setMaxWeight(parseFloat(e.target.value) / 100 || 1)}
                  className="input"
                  step={1}
                  min={0}
                  max={100}
                />
              </div>
            </>
          )}
        </div>
        {errors.weights && (
          <p className="text-danger text-xs">{errors.weights}</p>
        )}

        {/* Selected Assets Summary */}
        {selectedTickers.length > 0 && (
          <div className="bg-raised rounded-lg p-3">
            <p className="text-sm text-ink-secondary">
              <span className="font-medium">{selectedTickers.length}</span> assets selected:{" "}
              <span className="text-ink-muted">
                {selectedTickers.map((t) => t.label).join(", ")}
              </span>
            </p>
          </div>
        )}

        {/* Optimize Button */}
        <div className="flex justify-end pt-2">
          <button
            className="btn-primary"
            onClick={handleOptimize}
            disabled={isLoading || selectedTickers.length < 2}
          >
            {isLoading
              ? "Calculating..."
              : optimizationType === "correlation"
                ? "Run Analysis"
                : "Run Optimization"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default OptimizationConfig;
