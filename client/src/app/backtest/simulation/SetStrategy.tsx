import React, { useMemo, useState } from "react";
import {
  useFetchAlgorithmsQuery,
  useFetchTickersQuery,
  BacktestPayload,
} from "@/state/api";
import Select, { SingleValue, MultiValue } from "react-select";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

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
}

interface SetStrategyProps {
  onRunBacktest: (payload: BacktestPayload) => void;
  isLoading?: boolean;
}

// Custom styles for react-select to match our design system
const selectStyles = {
  control: (base: Record<string, unknown>, state: { isFocused: boolean }) => ({
    ...base,
    borderRadius: "0.5rem",
    borderWidth: "1px",
    borderColor: state.isFocused ? "#171717" : "#d4d4d4",
    padding: "0.125rem",
    boxShadow: state.isFocused ? "0 0 0 1px #171717" : "none",
    "&:hover": {
      borderColor: "#a3a3a3",
    },
    backgroundColor: "#fff",
    fontSize: "0.875rem",
  }),
  option: (
    base: Record<string, unknown>,
    state: { isSelected: boolean; isFocused: boolean }
  ) => ({
    ...base,
    backgroundColor: state.isSelected
      ? "#171717"
      : state.isFocused
        ? "#f5f5f5"
        : "transparent",
    color: state.isSelected ? "#fff" : "#171717",
    fontSize: "0.875rem",
    "&:active": {
      backgroundColor: "#e5e5e5",
    },
  }),
  multiValue: (base: Record<string, unknown>) => ({
    ...base,
    backgroundColor: "#f5f5f5",
    borderRadius: "0.375rem",
  }),
  multiValueLabel: (base: Record<string, unknown>) => ({
    ...base,
    color: "#171717",
    fontSize: "0.75rem",
    padding: "0.125rem 0.25rem",
  }),
  multiValueRemove: (base: Record<string, unknown>) => ({
    ...base,
    color: "#737373",
    "&:hover": {
      backgroundColor: "#e5e5e5",
      color: "#171717",
    },
  }),
  placeholder: (base: Record<string, unknown>) => ({
    ...base,
    color: "#a3a3a3",
    fontSize: "0.875rem",
  }),
};

const selectErrorStyles = {
  ...selectStyles,
  control: (base: Record<string, unknown>, state: { isFocused: boolean }) => ({
    ...base,
    borderRadius: "0.5rem",
    borderWidth: "1px",
    borderColor: "#FF5000",
    padding: "0.125rem",
    boxShadow: state.isFocused ? "0 0 0 1px #FF5000" : "none",
    "&:hover": {
      borderColor: "#FF5000",
    },
    backgroundColor: "#fff",
    fontSize: "0.875rem",
  }),
};

const SetStrategy: React.FC<SetStrategyProps> = ({
  onRunBacktest,
  isLoading = false,
}) => {
  const { data } = useFetchTickersQuery({});
  const { data: algorithmData } = useFetchAlgorithmsQuery({});
  const [startDate, setStartDate] = useState(new Date("2000-01-01"));
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

  const algorithmOptions = useMemo(
    () =>
      algorithmData
        ? algorithmData.map((alg: AlgorithmData) => ({
            value: alg.strategy,
            label: alg.strategy_name,
          }))
        : [],
    [algorithmData]
  );

  const handleIsoCodeChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedIsoCode(newValue);
  };

  const handleSecurityTypeChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedSecurityType(newValue);
  };

  const handleAlgorithmChange = (newValue: SingleValue<SelectOption>) => {
    setSelectedAlgorithm(newValue);
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
    }

    if (!selectedAlgorithm) {
      newErrors.algorithm = "Please select an algorithm";
    }

    if (startDate >= endDate) {
      newErrors.dates = "Start date must be before end date";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleButtonClick = () => {
    if (!validateForm()) return;

    const payload = {
      strategy_name: strategyName,
      meta_id: selectedTickers.map((meta_id) => meta_id.value),
      algorithm: selectedAlgorithm?.value,
      startDate: startDate.toISOString().split("T")[0],
      endDate: endDate.toISOString().split("T")[0],
    };
    onRunBacktest(payload);
  };

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-neutral-900 mb-6">
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
            onChange={(newValue) => {
              handleAlgorithmChange(newValue);
              if (errors.algorithm)
                setErrors((prev) => ({ ...prev, algorithm: undefined }));
            }}
            styles={errors.algorithm ? selectErrorStyles : selectStyles}
          />
          {errors.algorithm && (
            <p className="text-danger text-xs mt-1">{errors.algorithm}</p>
          )}
        </div>

        {/* Dates */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="input-label">Start Date</label>
            <DatePicker
              selected={startDate}
              onChange={(date) => {
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
              onChange={(date) => {
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

        {/* Run Button */}
        <div className="flex justify-end pt-2">
          <button
            className="btn-primary"
            onClick={handleButtonClick}
            disabled={isLoading}
          >
            {isLoading ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SetStrategy;
