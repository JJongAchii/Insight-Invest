"use client";

import TradingViewWidget from "@/app/(components)/TradingViewWidget";

const Home = () => {
  const tickerTapeUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
  const tickerTapeConfig = {
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
    isTransparent: true,
    displayMode: "compact",
    colorTheme: "light",
    locale: "en",
    scroll: true,
  };

  const marketQuotesUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js";
  const marketQuotesConfig = {
    width: "100%",
    height: "500",
    symbolsGroups: [
      {
        name: "Indices",
        originalName: "Indices",
        symbols: [
          { name: "FOREXCOM:SPXUSD", displayName: "S&P 500 Index" },
          { name: "FOREXCOM:NSXUSD", displayName: "US 100 Cash CFD" },
          { name: "FOREXCOM:DJI", displayName: "Dow Jones" },
          { name: "INDEX:NKY", displayName: "Japan 225" },
          { name: "INDEX:DEU40", displayName: "DAX Index" },
          { name: "FOREXCOM:UKXGBP", displayName: "FTSE 100 Index" },
        ],
      },
      {
        name: "Futures",
        originalName: "Futures",
        symbols: [
          { name: "CME:6E1!", displayName: "Euro" },
          { name: "COMEX:GC1!", displayName: "Gold" },
          { name: "NYMEX:CL1!", displayName: "WTI Crude Oil" },
          { name: "NYMEX:NG1!", displayName: "Gas" },
          { name: "CBOT:ZC1!", displayName: "Corn" },
        ],
      },
      {
        name: "Bonds",
        originalName: "Bonds",
        symbols: [
          { name: "CBOT:ZB1!", displayName: "T-Bond" },
          { name: "CBOT:UB1!", displayName: "Ultra T-Bond" },
          { name: "EUREX:FGBL1!", displayName: "Euro Bund" },
          { name: "EUREX:FBTP1!", displayName: "Euro BTP" },
          { name: "EUREX:FGBM1!", displayName: "Euro BOBL" },
        ],
      },
      {
        name: "Forex",
        originalName: "Forex",
        symbols: [
          { name: "FX:EURUSD", displayName: "EUR to USD" },
          { name: "FX:GBPUSD", displayName: "GBP to USD" },
          { name: "FX:USDJPY", displayName: "USD to JPY" },
          { name: "FX:USDCHF", displayName: "USD to CHF" },
          { name: "FX:AUDUSD", displayName: "AUD to USD" },
          { name: "FX:USDCAD", displayName: "USD to CAD" },
        ],
      },
    ],
    showSymbolLogo: true,
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    backgroundColor: "#ffffff",
  };

  const economicCalUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-events.js";
  const economicCalConfig = {
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    importanceFilter: "0,1",
    countryFilter: "us,eu,ch,kr,jp,cn",
    width: "100%",
    height: 500,
  };

  const fxCrossRateUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-forex-cross-rates.js";
  const fxCrossRateConfig = {
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    currencies: ["USD", "JPY", "CNY", "KRW", "EUR", "GBP", "CHF", "AUD"],
    width: "100%",
    height: 500,
  };

  const marketOverviewUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js";
  const marketOverviewConfig = {
    colorTheme: "light",
    dateRange: "12M",
    showChart: true,
    locale: "en",
    largeChartUrl: "",
    isTransparent: false,
    showSymbolLogo: true,
    showFloatingTooltip: false,
    width: "100%",
    height: "500",
    plotLineColorGrowing: "rgba(0, 200, 5, 1)",
    plotLineColorFalling: "rgba(255, 80, 0, 1)",
    gridLineColor: "rgba(240, 243, 250, 0)",
    scaleFontColor: "rgba(115, 115, 115, 1)",
    belowLineFillColorGrowing: "rgba(0, 200, 5, 0.08)",
    belowLineFillColorFalling: "rgba(255, 80, 0, 0.08)",
    belowLineFillColorGrowingBottom: "rgba(0, 200, 5, 0)",
    belowLineFillColorFallingBottom: "rgba(255, 80, 0, 0)",
    symbolActiveColor: "rgba(0, 200, 5, 0.08)",
    tabs: [
      {
        title: "Indices",
        symbols: [
          { s: "FOREXCOM:SPXUSD", d: "S&P 500 Index" },
          { s: "FOREXCOM:NSXUSD", d: "US 100 Cash CFD" },
          { s: "FOREXCOM:DJI", d: "Dow Jones" },
          { s: "INDEX:NKY", d: "Japan 225" },
          { s: "INDEX:DEU40", d: "DAX Index" },
          { s: "FOREXCOM:UKXGBP", d: "FTSE 100 Index" },
        ],
        originalTitle: "Indices",
      },
      {
        title: "Futures",
        symbols: [
          { s: "CME_MINI:ES1!", d: "S&P 500" },
          { s: "CME:6E1!", d: "Euro" },
          { s: "COMEX:GC1!", d: "Gold" },
          { s: "NYMEX:CL1!", d: "WTI Crude Oil" },
          { s: "NYMEX:NG1!", d: "Gas" },
          { s: "CBOT:ZC1!", d: "Corn" },
        ],
        originalTitle: "Futures",
      },
      {
        title: "Bonds",
        symbols: [
          { s: "CBOT:ZB1!", d: "T-Bond" },
          { s: "CBOT:UB1!", d: "Ultra T-Bond" },
          { s: "EUREX:FGBL1!", d: "Euro Bund" },
          { s: "EUREX:FBTP1!", d: "Euro BTP" },
          { s: "EUREX:FGBM1!", d: "Euro BOBL" },
        ],
        originalTitle: "Bonds",
      },
      {
        title: "Forex",
        symbols: [
          { s: "FX:EURUSD", d: "EUR to USD" },
          { s: "FX:GBPUSD", d: "GBP to USD" },
          { s: "FX:USDJPY", d: "USD to JPY" },
          { s: "FX:USDCHF", d: "USD to CHF" },
          { s: "FX:AUDUSD", d: "AUD to USD" },
          { s: "FX:USDCAD", d: "USD to CAD" },
        ],
        originalTitle: "Forex",
      },
    ],
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Dashboard</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Real-time market data and economic indicators
        </p>
      </div>

      {/* Ticker Tape */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <TradingViewWidget
          widgetScriptUrl={tickerTapeUrl}
          widgetConfig={tickerTapeConfig}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Economic Calendar */}
        <div className="card">
          <h3 className="text-base font-semibold text-neutral-900 mb-4">
            Economic Calendar
          </h3>
          <TradingViewWidget
            widgetScriptUrl={economicCalUrl}
            widgetConfig={economicCalConfig}
          />
        </div>

        {/* Market Data */}
        <div className="card">
          <h3 className="text-base font-semibold text-neutral-900 mb-4">
            Market Data
          </h3>
          <TradingViewWidget
            widgetScriptUrl={marketQuotesUrl}
            widgetConfig={marketQuotesConfig}
          />
        </div>

        {/* FX Cross Rates */}
        <div className="card">
          <h3 className="text-base font-semibold text-neutral-900 mb-4">
            FX Cross Rates
          </h3>
          <TradingViewWidget
            widgetScriptUrl={fxCrossRateUrl}
            widgetConfig={fxCrossRateConfig}
          />
        </div>

        {/* Market Overview */}
        <div className="card">
          <h3 className="text-base font-semibold text-neutral-900 mb-4">
            Market Overview
          </h3>
          <TradingViewWidget
            widgetScriptUrl={marketOverviewUrl}
            widgetConfig={marketOverviewConfig}
          />
        </div>
      </div>
    </div>
  );
};

export default Home;
