"use client";

import { useMemo } from "react";
import TradingViewWidget from "@/app/(components)/TradingViewWidget";
import { useAppSelector } from "@/app/redux";
import PageHeader from "@/components/ui/PageHeader";
import MarketTiles from "./MarketTiles";
import WatchlistCard from "./WatchlistCard";
import StrategiesCard from "./StrategiesCard";
import FlowsTopCard from "./FlowsTopCard";
import NewsCompactList from "./NewsCompactList";

const Home = () => {
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const colorTheme = isDarkMode ? "dark" : "light";

  const tickerTapeUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
  const tickerTapeConfig = useMemo(
    () => ({
      symbols: [
        { proName: "BITSTAMP:BTCUSD", title: "Bitcoin" },
        { description: "NASDAQ 100 Index", proName: "NASDAQ:NDX" },
        { description: "U.S. Dollar Index", proName: "CAPITALCOM:DXY" },
        { description: "S&P 500 Index", proName: "VANTAGE:SP500" },
        { description: "GOLD", proName: "OANDA:XAUUSD" },
        { description: "WTI CRUDE OIL", proName: "TVC:USOIL" },
        { description: "USD/KRW", proName: "FX_IDC:USDKRW" },
        { description: "USD/JPY", proName: "FX:USDJPY" },
        { description: "USD/CNY", proName: "FX_IDC:USDCNY" },
      ],
      showSymbolLogo: true,
      // 투명 배경은 우리 표면과 글자색이 어긋날 수 있어 TradingView 자체 테마 배경 사용
      isTransparent: false,
      displayMode: "compact",
      colorTheme,
      locale: "en",
      scroll: true,
    }),
    [colorTheme]
  );

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="나의 대시보드"
        description="시장 현황과 내 포트폴리오를 한눈에"
      />

      {/* Row 0: Ticker Tape */}
      <div className="rounded-xl border border-edge overflow-hidden">
        <TradingViewWidget
          key={`tape-${colorTheme}`}
          widgetScriptUrl={tickerTapeUrl}
          widgetConfig={tickerTapeConfig}
        />
      </div>

      {/* Row 1: Index snapshots + regime/gauge chips */}
      <MarketTiles />

      {/* Row 2: Watchlist + strategies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WatchlistCard />
        <StrategiesCard />
      </div>

      {/* Row 3: Foreign net-buy top 5 + latest news */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <FlowsTopCard />
        <NewsCompactList />
      </div>
    </div>
  );
};

export default Home;
