"use client";

import { useEffect, useRef, useState } from "react";
import { Globe2, RefreshCw } from "lucide-react";
import { useAppSelector } from "@/app/redux";
import styles from "./marketTicker.module.css";

const SCRIPT_URL = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
const SYMBOLS = [
  { description: "S&P 500 CFD", proName: "VANTAGE:SP500" },
  { description: "NASDAQ 100 CFD", proName: "VANTAGE:NAS100" },
  { description: "달러 인덱스", proName: "CAPITALCOM:DXY" },
  { description: "금", proName: "OANDA:XAUUSD" },
  { description: "WTI", proName: "TVC:USOIL" },
  { description: "USD/JPY", proName: "FX:USDJPY" },
  { description: "Bitcoin", proName: "BITSTAMP:BTCUSD" },
];

function TickerEmbed({ theme, onRetry }: { theme: "dark" | "light"; onRetry: () => void }) {
  const mount = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const root = mount.current;
    if (!root) return;
    // TradingView binds to the script's own parent; keep that DOM outside React.
    const container = document.createElement("div");
    container.className = "tradingview-widget-container";
    container.innerHTML = `<div class="tradingview-widget-container__widget"></div>
      <div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank"><span class="blue-text">Track all markets on TradingView</span></a><span> · 지연 가능</span></div>`;
    root.appendChild(container);
    let disposed = false;
    let frame: HTMLIFrameElement | null = null;
    const failed = () => { if (!disposed) setStatus("error"); };
    const timeout = window.setTimeout(failed, 15000);
    const ready = () => {
      window.clearTimeout(timeout);
      if (!disposed) setStatus("ready");
    };
    const onMessage = (event: MessageEvent) => {
      // A blocked iframe can still fire load. Wait for the official widget to
      // initialize, using the same resize message its embed script listens for.
      if (frame && event.source === frame.contentWindow &&
          event.origin === new URL(frame.src).origin &&
          event.data?.name === "tv-widget-resize-iframe") ready();
    };
    window.addEventListener("message", onMessage);
    const observer = new MutationObserver(() => {
      const iframe = container.querySelector("iframe");
      if (!iframe || iframe === frame) return;
      frame = iframe;
      frame.title = "글로벌 시장 시세 — TradingView";
    });
    observer.observe(container, { childList: true, subtree: true });
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    script.onerror = failed;
    script.textContent = JSON.stringify({
      symbols: SYMBOLS,
      showSymbolLogo: false,
      isTransparent: false,
      // Regular keeps a single price row on mobile as well as desktop.
      displayMode: "regular",
      colorTheme: theme,
      locale: "kr",
    });
    container.appendChild(script);
    return () => {
      disposed = true;
      window.clearTimeout(timeout);
      observer.disconnect();
      window.removeEventListener("message", onMessage);
      script.onerror = null;
      container.remove();
    };
  }, [theme]);

  return <div className={styles.embed} data-status={status}>
    <div ref={mount} className={status === "error" ? "hidden" : undefined} />
    {status !== "ready" && <div className={styles.status} role="status">
      <div>
        <p>{status === "loading" ? "글로벌 시세를 연결하고 있습니다…" : "글로벌 시세에 연결하지 못했습니다"}</p>
        <a href="https://www.tradingview.com/markets/" target="_blank" rel="noopener noreferrer">TradingView에서 시장 보기 ↗</a>
      </div>
      {status === "error" && <button type="button" onClick={onRetry} className="btn-secondary inline-flex shrink-0 items-center gap-1.5 text-xs">
        <RefreshCw size={13} aria-hidden />다시 시도
      </button>}
    </div>}
  </div>;
}

export default function MarketTicker() {
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const isSidebarCollapsed = useAppSelector((state) => state.global.isSidebarCollapsed);
  const [attempt, setAttempt] = useState(0);
  const theme = isDarkMode ? "dark" : "light";

  return <aside aria-label="글로벌 시장 시세" className={`${styles.bar} ${isSidebarCollapsed ? styles.collapsed : ""}`}>
    <div className={styles.label}><Globe2 size={15} aria-hidden /><span>글로벌 시세</span></div>
    <TickerEmbed key={`${theme}-${attempt}`} theme={theme} onRetry={() => setAttempt((value) => value + 1)} />
  </aside>;
}
