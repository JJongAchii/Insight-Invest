"use client"

import TradingViewWidget from "@/app/(components)/TradingViewWidget";


const Home = () => {
  const tickerTapeUrl = 'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
  const tickerTapeConfig = {
    symbols: [
      {
        "proName": "BITSTAMP:BTCUSD",
        "title": "Bitcoin"
      },
      {
        "description": "NASDAQ 100 Index",
        "proName": "NASDAQ:NDX"
      },
      {
        "description": "U.S. Dollar Index",
        "proName": "CAPITALCOM:DXY"
      },
      {
        "description": "s&P 500 Index",
        "proName": "VANTAGE:SP500"
      },
      {
        "description": "GOLD",
        "proName": "OANDA:XAUUSD"
      },
      {
        "description": "WTI CRUDE OIL",
        "proName": "TVC:USOIL"
      },
      {
        "description": "USD/KRW",
        "proName": "FX_IDC:USDKRW"
      },
      {
        "description": "USD/JPY",
        "proName": "FX:USDJPY"
      },
      {
        "description": "USD/CNY",
        "proName": "FX_IDC:USDCNY"
      }
    ],
    showSymbolLogo: true,
    isTransparent: false,
    displayMode: 'compact',
    colorTheme: 'light',
    locale: 'en',
    scroll: true,
  }

  const marketQuotesUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-market-quotes.js";
  const marketQuotesConfig = {
    width: "100%", // Adjust as needed
    height: "500",
    symbolsGroups: [
      {
        name: "Indices",
        originalName: "Indices",
        symbols: [
          {
            name: "FOREXCOM:SPXUSD",
            displayName: "S&P 500 Index",
          },
          {
            name: "FOREXCOM:NSXUSD",
            displayName: "US 100 Cash CFD",
          },
          {
            name: "FOREXCOM:DJI",
            displayName: "Dow Jones Industrial Average Index",
          },
          {
            name: "INDEX:NKY",
            displayName: "Japan 225",
          },
          {
            name: "INDEX:DEU40",
            displayName: "DAX Index",
          },
          {
            name: "FOREXCOM:UKXGBP",
            displayName: "FTSE 100 Index",
          },
        ],
      },
      {
        name: "Futures",
        originalName: "Futures",
        symbols: [
          {
            name: "CME:6E1!",
            displayName: "Euro",
          },
          {
            name: "COMEX:GC1!",
            displayName: "Gold",
          },
          {
            name: "NYMEX:CL1!",
            displayName: "WTI Crude Oil",
          },
          {
            name: "NYMEX:NG1!",
            displayName: "Gas",
          },
          {
            name: "CBOT:ZC1!",
            displayName: "Corn",
          },
        ],
      },
      {
        name: "Bonds",
        originalName: "Bonds",
        symbols: [
          {
            name: "CBOT:ZB1!",
            displayName: "T-Bond",
          },
          {
            name: "CBOT:UB1!",
            displayName: "Ultra T-Bond",
          },
          {
            name: "EUREX:FGBL1!",
            displayName: "Euro Bund",
          },
          {
            name: "EUREX:FBTP1!",
            displayName: "Euro BTP",
          },
          {
            name: "EUREX:FGBM1!",
            displayName: "Euro BOBL",
          },
        ],
      },
      {
        name: "Forex",
        originalName: "Forex",
        symbols: [
          {
            name: "FX:EURUSD",
            displayName: "EUR to USD",
          },
          {
            name: "FX:GBPUSD",
            displayName: "GBP to USD",
          },
          {
            name: "FX:USDJPY",
            displayName: "USD to JPY",
          },
          {
            name: "FX:USDCHF",
            displayName: "USD to CHF",
          },
          {
            name: "FX:AUDUSD",
            displayName: "AUD to USD",
          },
          {
            name: "FX:USDCAD",
            displayName: "USD to CAD",
          },
        ],
      },
    ],
    showSymbolLogo: true,
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    backgroundColor: "#ffffff",
  };

  const economicCalUrl = "https://s3.tradingview.com/external-embedding/embed-widget-events.js";
  const economicCalConfig = {
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    importanceFilter: "0,1",
    countryFilter: "us,eu,ch,kr,jp,cn",
    width: "100%",
    height: 500,
  }

  const fxCrossRateUrl = "https://s3.tradingview.com/external-embedding/embed-widget-forex-cross-rates.js";
  const fxCrossRateConfig = {
    isTransparent: false,
    colorTheme: "light",
    locale: "en",
    currencies: ["USD","JPY","CNY","KRW","EUR","GBP","CHF","AUD"],
    width: "100%",
    height: 500,
  }

  const marketOverviewUrl = "https://s3.tradingview.com/external-embedding/embed-widget-market-overview.js";
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
    plotLineColorGrowing: "rgba(41, 98, 255, 1)",
    plotLineColorFalling: "rgba(41, 98, 255, 1)",
    gridLineColor: "rgba(240, 243, 250, 0)",
    scaleFontColor: "rgba(19, 23, 34, 1)",
    belowLineFillColorGrowing: "rgba(41, 98, 255, 0.12)",
    belowLineFillColorFalling: "rgba(41, 98, 255, 0.12)",
    belowLineFillColorGrowingBottom: "rgba(41, 98, 255, 0)",
    belowLineFillColorFallingBottom: "rgba(41, 98, 255, 0)",
    symbolActiveColor: "rgba(41, 98, 255, 0.12)",
    tabs: [
      {
        title: "Indices",
        symbols: [
          {
            s: "FOREXCOM:SPXUSD",
            d: "S&P 500 Index",
          },
          {
            s: "FOREXCOM:NSXUSD",
            d: "US 100 Cash CFD",
          },
          {
            s: "FOREXCOM:DJI",
            d: "Dow Jones Industrial Average Index",
          },
          {
            s: "INDEX:NKY",
            d: "Japan 225",
          },
          {
            s: "INDEX:DEU40",
            d: "DAX Index",
          },
          {
            s: "FOREXCOM:UKXGBP",
            d: "FTSE 100 Index",
          },
        ],
        originalTitle: "Indices",
      },
      {
        title: "Futures",
        symbols: [
          {
            s: "CME_MINI:ES1!",
            d: "S&P 500",
          },
          {
            s: "CME:6E1!",
            d: "Euro",
          },
          {
            s: "COMEX:GC1!",
            d: "Gold",
          },
          {
            s: "NYMEX:CL1!",
            d: "WTI Crude Oil",
          },
          {
            s: "NYMEX:NG1!",
            d: "Gas",
          },
          {
            s: "CBOT:ZC1!",
            d: "Corn",
          },
        ],
        originalTitle: "Futures",
      },
      {
        title: "Bonds",
        symbols: [
          {
            s: "CBOT:ZB1!",
            d: "T-Bond",
          },
          {
            s: "CBOT:UB1!",
            d: "Ultra T-Bond",
          },
          {
            s: "EUREX:FGBL1!",
            d: "Euro Bund",
          },
          {
            s: "EUREX:FBTP1!",
            d: "Euro BTP",
          },
          {
            s: "EUREX:FGBM1!",
            d: "Euro BOBL",
          },
        ],
        originalTitle: "Bonds",
      },
      {
        title: "Forex",
        symbols: [
          {
            s: "FX:EURUSD",
            d: "EUR to USD",
          },
          {
            s: "FX:GBPUSD",
            d: "GBP to USD",
          },
          {
            s: "FX:USDJPY",
            d: "USD to JPY",
          },
          {
            s: "FX:USDCHF",
            d: "USD to CHF",
          },
          {
            s: "FX:AUDUSD",
            d: "AUD to USD",
          },
          {
            s: "FX:USDCAD",
            d: "USD to CAD",
          },
        ],
        originalTitle: "Forex",
      },
    ],
  };
  

  return (
    <div className="flex flex-col gap-5">
      <TradingViewWidget 
        widgetScriptUrl={tickerTapeUrl}
        widgetConfig={tickerTapeConfig}
      />
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
          <h4 className="text-lg font-semibold">Economic Calendar</h4>
          <TradingViewWidget
            widgetScriptUrl={economicCalUrl}
            widgetConfig={economicCalConfig}
          />
        </div>
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
          <h4 className="text-lg font-semibold">Market Data</h4>
          <TradingViewWidget
            widgetScriptUrl={marketQuotesUrl}
            widgetConfig={marketQuotesConfig}
          />
        </div>
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
          <h4 className="text-lg font-semibold">Forex Cross Rate</h4>
          <TradingViewWidget 
            widgetScriptUrl={fxCrossRateUrl}
            widgetConfig={fxCrossRateConfig}
          />
        </div>
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
          <h4 className="text-lg font-semibold">Market Overview</h4>
          <TradingViewWidget
            widgetScriptUrl={marketOverviewUrl}
            widgetConfig={marketOverviewConfig}
          />
        </div>
      </div>
    </div>
);
}

export default Home
