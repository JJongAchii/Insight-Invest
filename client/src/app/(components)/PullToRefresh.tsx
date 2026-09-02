"use client";

import { ArrowDown, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
  isScrollableRegion,
  measurePullMovement,
} from "@/lib/pullToRefresh.mjs";

type PullPhase = "idle" | "pulling" | "armed" | "refreshing";

type PullView = {
  phase: PullPhase;
  distance: number;
  progress: number;
};

const INITIAL_VIEW: PullView = { phase: "idle", distance: 0, progress: 0 };

function isDocumentAtTop() {
  return (document.scrollingElement?.scrollTop ?? window.scrollY) <= 0;
}

function startsInsideScrollableElement(target: EventTarget | null) {
  let element = target instanceof Element ? target : null;

  if (
    element?.closest(
      "input, textarea, select, [contenteditable='true'], [data-pull-refresh-ignore]"
    )
  ) {
    return true;
  }

  while (
    element &&
    element !== document.body &&
    element !== document.documentElement
  ) {
    const overflowY = window.getComputedStyle(element).overflowY;
    if (
      isScrollableRegion({
        overflowY,
        scrollHeight: element.scrollHeight,
        clientHeight: element.clientHeight,
      })
    ) {
      return true;
    }
    element = element.parentElement;
  }

  return false;
}

export default function PullToRefresh() {
  const [view, setView] = useState<PullView>(INITIAL_VIEW);
  const gesture = useRef({ active: false, startX: 0, startY: 0 });
  const armed = useRef(false);
  const reloadTimer = useRef<number | null>(null);

  useEffect(() => {
    const touchDevice =
      navigator.maxTouchPoints > 0 &&
      window.matchMedia("(pointer: coarse)").matches;
    if (!touchDevice) return;

    const reset = () => {
      gesture.current.active = false;
      armed.current = false;
      setView(INITIAL_VIEW);
    };

    const onTouchStart = (event: TouchEvent) => {
      if (
        event.touches.length !== 1 ||
        !isDocumentAtTop() ||
        startsInsideScrollableElement(event.target) ||
        (window.visualViewport?.scale ?? 1) > 1.01
      ) {
        return;
      }

      const touch = event.touches[0];
      gesture.current = {
        active: true,
        startX: touch.clientX,
        startY: touch.clientY,
      };
    };

    const onTouchMove = (event: TouchEvent) => {
      if (!gesture.current.active || event.touches.length !== 1) return;

      const touch = event.touches[0];
      const movement = measurePullMovement({
        startX: gesture.current.startX,
        startY: gesture.current.startY,
        currentX: touch.clientX,
        currentY: touch.clientY,
      });

      if (movement.direction === "pending") return;
      if (movement.direction === "cancelled" || !isDocumentAtTop()) {
        reset();
        return;
      }

      event.preventDefault();
      armed.current = movement.armed;
      setView({
        phase: movement.armed ? "armed" : "pulling",
        distance: movement.visualDistance,
        progress: movement.progress,
      });
    };

    const onTouchEnd = () => {
      if (!gesture.current.active) return;
      gesture.current.active = false;

      if (!armed.current) {
        reset();
        return;
      }

      armed.current = false;
      setView({ phase: "refreshing", distance: 36, progress: 1 });
      reloadTimer.current = window.setTimeout(() => window.location.reload(), 180);
    };

    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    window.addEventListener("touchcancel", reset, { passive: true });

    return () => {
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("touchcancel", reset);
      if (reloadTimer.current !== null) window.clearTimeout(reloadTimer.current);
    };
  }, []);

  if (view.phase === "idle") return null;

  const refreshing = view.phase === "refreshing";
  const label = refreshing
    ? "Refreshing…"
    : view.phase === "armed"
      ? "Release to refresh"
      : "Pull to refresh";

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed left-1/2 z-[80] flex items-center gap-2 rounded-full border border-edge-strong bg-overlay/95 px-3 py-2 text-xs font-medium text-ink shadow-xl backdrop-blur"
      style={{
        top: "calc(env(safe-area-inset-top) + 0.5rem)",
        transform: `translate(-50%, ${view.distance}px)`,
      }}
    >
      {refreshing ? (
        <RefreshCw size={15} className="animate-spin motion-reduce:animate-none" />
      ) : (
        <ArrowDown
          size={15}
          className={view.phase === "armed" ? "text-primary-400" : "text-ink-muted"}
          style={{ transform: `rotate(${view.progress * 180}deg)` }}
        />
      )}
      <span>{label}</span>
    </div>
  );
}
