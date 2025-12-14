"use client";

import { useEffect, useState } from "react";
import SetStrategy from "./SetStrategy";
import StrategyChart from "./StrategyChart";
import StrategyMetrics from "./StrategyMetrics";
import LoadingSpinner from "@/app/(components)/LoadingSpinner";
import {
  useRunBacktestMutation,
  useClearStrategyMutation,
  BacktestPayload,
  BacktestResult,
} from "@/state/api";

const Simulation = () => {
  const [runBacktest, { isLoading }] = useRunBacktestMutation();
  const [clearStrategy, { isLoading: isClearing }] = useClearStrategyMutation();
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  const [selectedTicker, setSelectedTicker] = useState<
    Record<string, BacktestPayload>
  >(() => {
    if (typeof window === "undefined") return {};
    const savedTicker = localStorage.getItem("selectedTicker");
    return savedTicker ? JSON.parse(savedTicker) : {};
  });
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(
    () => {
      if (typeof window === "undefined") return null;
      const savedResult = localStorage.getItem("backtestResult");
      return savedResult ? JSON.parse(savedResult) : null;
    }
  );

  const handleRunBacktest = async (payload: BacktestPayload) => {
    try {
      const result = await runBacktest(payload).unwrap();
      setBacktestResult(result);
      setSelectedTicker((prevSelectedTicker) => ({
        ...prevSelectedTicker,
        [payload.strategy_name]: payload,
      }));
    } catch (error) {
      console.error("Error running backtest:", error);
      setBacktestResult(null);
    }
  };

  useEffect(() => {
    localStorage.setItem("backtestResult", JSON.stringify(backtestResult));
  }, [backtestResult]);

  useEffect(() => {
    localStorage.setItem("selectedTicker", JSON.stringify(selectedTicker));
  }, [selectedTicker]);

  const handleClearClick = () => {
    setShowClearConfirm(true);
  };

  const confirmClear = async () => {
    localStorage.removeItem("backtestResult");
    localStorage.removeItem("selectedTicker");
    setBacktestResult(null);
    setSelectedTicker({});
    try {
      await clearStrategy().unwrap();
    } catch (error) {
      console.error("Error clearing strategy:", error);
    }
    setShowClearConfirm(false);
  };

  const cancelClear = () => {
    setShowClearConfirm(false);
  };

  return (
    <div className="flex flex-col gap-6 pb-16">
      {isLoading && <LoadingSpinner />}

      {/* Clear Confirmation Modal */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-neutral-900 mb-2">
              Clear All Strategies?
            </h3>
            <p className="text-neutral-600 text-sm mb-6">
              This will remove all backtest results and selected tickers. This
              action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button onClick={cancelClear} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={confirmClear}
                disabled={isClearing}
                className="btn-danger"
              >
                {isClearing ? "Clearing..." : "Clear All"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            Backtest Simulation
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Test your investment strategies with historical data
          </p>
        </div>
        <button
          onClick={handleClearClick}
          disabled={isLoading || isClearing}
          className="btn-danger"
        >
          Clear All
        </button>
      </div>

      <SetStrategy onRunBacktest={handleRunBacktest} isLoading={isLoading} />
      <StrategyChart navResult={backtestResult?.nav ?? null} />
      <StrategyMetrics
        backtestResult={backtestResult}
        selectedTicker={selectedTicker}
      />
    </div>
  );
};

export default Simulation;
