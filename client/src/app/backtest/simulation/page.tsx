"use client"

import { useEffect, useState } from "react";
import SetStrategy from "./SetStrategy";
import StrategyChart from "./StrategyChart";
import { BacktestFetcher, ClearStrategy } from "./BacktestFetcher";
import StrategyMetrics from "./StrategyMetrics";
import { Result } from "postcss";
import LoadingSpinner from "@/app/(components)/LoadingSpinner";


const Simulation = () => {
    
    const [loading, setLoading] = useState(false);

    const [selectedTicker, setSelectedTicker] = useState(() => {
        const savedTicker = localStorage.getItem("selectedTicker");
        return savedTicker ? JSON.parse(savedTicker) : {};
    });
    const [backtestResult, setBacktestResult] = useState(() => {
        
        const savedResult = localStorage.getItem("backtestResult");
        return savedResult ? JSON.parse(savedResult) : [];
    });

    const handleRunBacktest = (payload: any) => {
        setLoading(true);
        BacktestFetcher(payload, (result: any) => {
            setBacktestResult(result);
            setLoading(false)
        });
        setSelectedTicker((prevSelectedTicker: any) => ({
            ...prevSelectedTicker,
            [payload.strategy_name]: payload // Use strategy_name as the key
        }));
    };

    useEffect(() => {
        localStorage.setItem("backtestResult", JSON.stringify(backtestResult));
    }, [backtestResult]);

    useEffect(() => {
        localStorage.setItem("selectedTicker", JSON.stringify(selectedTicker));
    }, [selectedTicker]);

    const clearCache = () => {
        localStorage.removeItem("backtestResult");
        localStorage.removeItem("selectedTicker");
        setBacktestResult([]); // Reset the state as well
        setSelectedTicker({}); // Reset the state as well
        ClearStrategy()
    };

    return (
        <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
            {loading && <LoadingSpinner />}
            <h2 className="text-4xl font-bold px-7 pt-7">Backtesting Tool</h2>
            <button onClick={clearCache} className="px-4 py-2 bg-red-500 text-white rounded">
                Clear Strategy
            </button>
            <SetStrategy onRunBacktest ={handleRunBacktest}/>
            <StrategyChart navResult={backtestResult?.nav}/>
            <StrategyMetrics backtestResult={backtestResult} selectedTicker={selectedTicker} />
        </div>
    );
}

export default Simulation