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
    const [clearStrategy] = useClearStrategyMutation();

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

    const clearCache = async () => {
        localStorage.removeItem("backtestResult");
        localStorage.removeItem("selectedTicker");
        setBacktestResult(null);
        setSelectedTicker({});
        try {
            await clearStrategy().unwrap();
        } catch (error) {
            console.error('Error clearing strategy:', error);
        }
    };

    return (
        <div className="flex flex-col xl:overflow-auto gap-8 pb-36">
            {isLoading && <LoadingSpinner />}

            {/* Page Header */}
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h1 className="text-4xl font-bold mb-2">
                        <span className="gradient-text">Backtesting Simulation</span>
                    </h1>
                    <p className="text-gray-600 text-lg">Test your investment strategies with historical data</p>
                </div>
                <button
                    onClick={clearCache}
                    className="px-6 py-3 bg-gradient-to-r from-red-500 to-pink-600 text-white rounded-xl font-semibold shadow-md hover:shadow-lg hover:from-red-600 hover:to-pink-700 transition-all duration-300"
                >
                    Clear Strategy
                </button>
            </div>

            <SetStrategy onRunBacktest={handleRunBacktest}/>
            <StrategyChart navResult={backtestResult?.nav ?? null}/>
            <StrategyMetrics backtestResult={backtestResult} selectedTicker={selectedTicker} />
        </div>
    );
}

export default Simulation
