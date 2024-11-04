"use client"

import { useEffect, useState } from "react";
import SetStrategy from "./SetStrategy";
import StrategyChart from "./StrategyChart";
import BacktestFetcher from "./BacktestFetcher";
import StrategyMetrics from "./StrategyMetrics";

const Backtest = () => {
    
    const [backtestResult, setBacktestResult] = useState(() => {
        
        const savedResult = localStorage.getItem("backtestResult");
        return savedResult ? JSON.parse(savedResult) : [];
    });

    const handleRunBacktest = (payload) => {
        BacktestFetcher(payload, setBacktestResult);
    };

    useEffect(() => {
        localStorage.setItem("backtestResult", JSON.stringify(backtestResult));
    }, [backtestResult]);

    return (
        <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
            <h2 className="text-4xl font-bold px-7 pt-7">Backtesting Tool</h2>
            <SetStrategy onRunBacktest ={handleRunBacktest}/>
            <StrategyChart navResult={backtestResult?.nav}/>
            <StrategyMetrics metricsResult={backtestResult?.metrics}/>
        </div>
    );
}

export default Backtest