import React from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { useRouter } from "next/navigation";

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip);

interface Strategy {
  port_id: number;
  port_name: string;
  strategy_name: string;
  ann_ret: number;
  ann_vol: number;
  sharpe: number;
}

interface StrategyNav {
  port_id: number;
  trade_date: string;
  value: number;
}

const Contents = ({
  strategyList,
  strategyNav,
}: {
  strategyList: Strategy[];
  strategyNav: StrategyNav[];
}) => {
  const router = useRouter();
  const handleGridClick = (port_id: number) => {
    router.push(`/backtest/strategy_list/${port_id}`);
  };

  if (!strategyList || strategyList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-neutral-400 text-sm">No strategies found</p>
        <p className="text-neutral-400 text-xs mt-1">
          Run a backtest and save it to see it here
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
      {strategyList?.map((strategy) => (
        <div
          key={strategy.port_id}
          className="flex bg-white p-5 rounded-xl border border-neutral-200 hover:border-neutral-300 cursor-pointer transition-colors duration-150"
          onClick={() => handleGridClick(strategy.port_id)}
        >
          <div className="w-1/2 pr-4">
            <div className="font-semibold text-neutral-900 mb-1">
              {strategy.port_name}
            </div>
            <div className="text-neutral-500 text-xs mb-3">
              {strategy.strategy_name}
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Return</span>
                <span
                  className={`text-sm font-medium ${
                    strategy.ann_ret >= 0 ? "text-success" : "text-danger"
                  }`}
                >
                  {strategy.ann_ret >= 0 ? "+" : ""}
                  {strategy.ann_ret}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Volatility</span>
                <span className="text-sm font-medium text-neutral-700">
                  {strategy.ann_vol}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-500">Sharpe</span>
                <span className="text-sm font-medium text-neutral-700">
                  {strategy.sharpe}
                </span>
              </div>
            </div>
          </div>
          <div className="w-1/2 flex items-center">
            <Line
              data={{
                labels: strategyNav
                  ?.filter((nav) => nav.port_id === strategy.port_id)
                  .map((nav) => nav.trade_date),
                datasets: [
                  {
                    label: "Value",
                    data: strategyNav
                      ?.filter((nav) => nav.port_id === strategy.port_id)
                      .map((nav) => nav.value),
                    fill: true,
                    backgroundColor: "rgba(23, 23, 23, 0.05)",
                    borderColor: "#171717",
                    borderWidth: 1.5,
                    tension: 0.3,
                    pointRadius: 0,
                  },
                ],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                  x: { display: false },
                  y: { display: false },
                },
                plugins: {
                  legend: { display: false },
                  tooltip: {
                    enabled: true,
                    backgroundColor: "rgba(255, 255, 255, 0.98)",
                    titleColor: "#171717",
                    bodyColor: "#737373",
                    borderColor: "#e5e5e5",
                    borderWidth: 1,
                    padding: 8,
                    cornerRadius: 6,
                  },
                },
              }}
              height={60}
            />
          </div>
        </div>
      ))}
    </div>
  );
};

export default Contents;
