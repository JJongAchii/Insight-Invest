"use client"

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

    const [selectedTicker, setSelectedTicker] = useState<Record<string, BacktestPayload>>(() => {
        if (typeof window === 'undefined') return {};
        const savedTicker = localStorage.getItem("selectedTicker");
        return savedTicker ? JSON.parse(savedTicker) : {};
    });
    const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(() => {
        if (typeof window === 'undefined') return null;
        const savedResult = localStorage.getItem("backtestResult");
        return savedResult ? JSON.parse(savedResult) : null;
    });

    const handleRunBacktest = async (payload: BacktestPayload) => {
        try {
            const result = await runBacktest(payload).unwrap();
            setBacktestResult(result);
            setSelectedTicker((prevSelectedTicker) => ({
                ...prevSelectedTicker,
                [payload.strategy_name]: payload
            }));
        } catch (error) {
            console.error('Error running backtest:', error);
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
            console.error('Error clearing strategy:', error);
        }
        setShowClearConfirm(false);
    };

    const cancelClear = () => {
        setShowClearConfirm(false);
    };

    return (
        <div className="flex flex-col xl:overflow-auto gap-8 pb-36">
            {isLoading && <LoadingSpinner />}

            {/* Clear Confirmation Dialog */}
            {showClearConfirm && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-2xl p-6 max-w-md mx-4 shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                                <span className="text-2xl">⚠️</span>
                            </div>
                            <h3 className="text-xl font-bold text-gray-800">Clear All Strategies?</h3>
                        </div>
                        <p className="text-gray-600 mb-6">
                            This will remove all backtest results and selected tickers. This action cannot be undone.
                        </p>
                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={cancelClear}
                                className="px-4 py-2 border-2 border-gray-300 text-gray-700 rounded-xl font-semibold hover:bg-gray-50 transition-all duration-300"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmClear}
                                disabled={isClearing}
                                className="px-4 py-2 bg-gradient-to-r from-red-500 to-pink-600 text-white rounded-xl font-semibold shadow-md hover:shadow-lg hover:from-red-600 hover:to-pink-700 transition-all duration-300 disabled:opacity-50"
                            >
                                {isClearing ? 'Clearing...' : 'Yes, Clear All'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Page Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-4xl font-bold mb-2">
                        <span className="gradient-text">Backtesting Simulation</span>
                    </h1>
                    <p className="text-gray-600 text-lg">Test your investment strategies with historical data</p>
                </div>
                <button
                    onClick={handleClearClick}
                    disabled={isLoading || isClearing}
                    className="px-6 py-3 bg-gradient-to-r from-red-500 to-pink-600 text-white rounded-xl font-semibold shadow-md hover:shadow-lg hover:from-red-600 hover:to-pink-700 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Clear Strategy
                </button>
            </div>

            <SetStrategy onRunBacktest={handleRunBacktest} isLoading={isLoading} />
            <StrategyChart navResult={backtestResult?.nav ?? null}/>
            <StrategyMetrics backtestResult={backtestResult} selectedTicker={selectedTicker} />
        </div>
    );
}

export default Simulation
