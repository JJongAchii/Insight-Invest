"use client"

import SetStrategy from "./SetStrategy";

const Backtest = () => {
    return (
        <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
            <h2 className="text-4xl font-bold px-7 pt-7">Backtesting Tool</h2>
            <SetStrategy />
        </div>
    );
}

export default Backtest