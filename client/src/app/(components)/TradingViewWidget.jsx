// components/TradingViewWidget.js
import { useEffect, useRef } from 'react';

const TradingViewWidget = ({ widgetScriptUrl, widgetConfig }) => {
    const containerRef = useRef(null);

    useEffect(() => {
        if (typeof window !== 'undefined' && containerRef.current) {
            containerRef.current.innerHTML = '';
            const script = document.createElement('script');
            script.src = widgetScriptUrl;
            script.async = true;
            script.innerHTML = JSON.stringify(widgetConfig);
            containerRef.current.appendChild(script);
        }
    }, [widgetScriptUrl, widgetConfig]);

    return (
        <div className="tradingview-widget-container" ref={containerRef}>
        <div className="tradingview-widget-container__widget"></div>
        <div className="tradingview-widget-copyright">
            <a
            href="https://www.tradingview.com/"
            rel="noopener nofollow"
            target="_blank"
            >
            <span className="blue-text">Track all markets on TradingView</span>
            </a>
        </div>
        </div>
    );
};

export default TradingViewWidget;
