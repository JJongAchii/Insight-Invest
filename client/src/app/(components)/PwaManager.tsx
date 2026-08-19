"use client";

import { Download, RefreshCw, Share, X } from "lucide-react";
import { useEffect, useState } from "react";

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const INSTALL_DISMISSED_AT = "ii-install-dismissed-at";
const DISMISS_FOR_MS = 7 * 24 * 60 * 60 * 1000;

export default function PwaManager() {
  const [showIosGuide, setShowIosGuide] = useState(false);
  const [installPrompt, setInstallPrompt] =
    useState<InstallPromptEvent | null>(null);
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    const standalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);
    const ios =
      /iphone|ipad|ipod/i.test(window.navigator.userAgent) ||
      (window.navigator.platform === "MacIntel" &&
        window.navigator.maxTouchPoints > 1);
    const dismissedAt = Number(localStorage.getItem(INSTALL_DISMISSED_AT) || 0);
    if (ios && !standalone && Date.now() - dismissedAt > DISMISS_FOR_MS) {
      setShowIosGuide(true);
    }

    const captureInstallPrompt = (event: Event) => {
      event.preventDefault();
      if (!standalone) setInstallPrompt(event as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", captureInstallPrompt);
    return () =>
      window.removeEventListener("beforeinstallprompt", captureInstallPrompt);
  }, []);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) {
      return;
    }

    let reloading = false;
    const onControllerChange = () => {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    navigator.serviceWorker.register("/sw.js").then((registration) => {
      if (registration.waiting) setWaitingWorker(registration.waiting);
      registration.addEventListener("updatefound", () => {
        const worker = registration.installing;
        if (!worker) return;
        worker.addEventListener("statechange", () => {
          if (worker.state === "installed" && navigator.serviceWorker.controller) {
            setWaitingWorker(worker);
          }
        });
      });
    });

    return () =>
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
  }, []);

  const dismissGuide = () => {
    localStorage.setItem(INSTALL_DISMISSED_AT, String(Date.now()));
    setShowIosGuide(false);
  };

  const install = async () => {
    if (!installPrompt) return;
    await installPrompt.prompt();
    await installPrompt.userChoice;
    setInstallPrompt(null);
  };

  return (
    <>
      {(showIosGuide || installPrompt) && (
        <aside className="fixed inset-x-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-[60] mx-auto max-w-md rounded-2xl border border-edge-strong bg-overlay p-4 shadow-2xl md:bottom-6 md:left-auto md:right-6 md:mx-0">
          <button
            type="button"
            onClick={dismissGuide}
            aria-label="설치 안내 닫기"
            className="absolute right-3 top-3 rounded-lg p-1 text-ink-muted hover:bg-raised hover:text-ink"
          >
            <X size={17} />
          </button>
          <div className="flex gap-3 pr-7">
            <div className="mt-0.5 rounded-xl bg-primary-500/15 p-2 text-primary-400">
              {showIosGuide ? <Share size={20} /> : <Download size={20} />}
            </div>
            <div>
              <h2 className="font-semibold text-ink">Install Insight Invest</h2>
              {showIosGuide ? (
                <p className="mt-1 text-sm leading-5 text-ink-secondary">
                  Safari의 공유 버튼을 누른 뒤 <strong>홈 화면에 추가</strong>와
                  <strong> 웹 앱으로 열기</strong>를 선택하세요.
                </p>
              ) : (
                <button type="button" onClick={install} className="btn-primary mt-3">
                  Add to Home Screen
                </button>
              )}
            </div>
          </div>
        </aside>
      )}

      {waitingWorker && (
        <aside className="fixed inset-x-4 top-[calc(1rem+env(safe-area-inset-top))] z-[70] mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl border border-edge-strong bg-overlay p-4 shadow-2xl">
          <div className="flex items-center gap-3">
            <RefreshCw size={19} className="text-primary-400" />
            <div>
              <h2 className="text-sm font-semibold text-ink">Update Ready</h2>
              <p className="text-xs text-ink-muted">새 버전을 다시 불러올 수 있습니다.</p>
            </div>
          </div>
          <button
            type="button"
            className="btn-primary whitespace-nowrap px-3 py-2 text-sm"
            onClick={() => waitingWorker.postMessage({ type: "SKIP_WAITING" })}
          >
            Reload
          </button>
        </aside>
      )}
    </>
  );
}
