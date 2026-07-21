"use client";

import React, { useEffect, useRef, useState } from "react";
import { Info } from "lucide-react";
import { INDICATOR_HELP } from "@/content/indicatorHelp";

interface InfoTipProps {
  /** Key into INDICATOR_HELP. If missing (and no children), renders nothing. */
  helpKey?: string;
  /** Custom popover content, overrides the dictionary lookup. */
  children?: React.ReactNode;
  className?: string;
}

/**
 * Accessible indicator-explanation popover.
 * Opens on hover/focus (desktop) and tap-toggle (touch); closes on outside
 * click or Escape. Rendered entirely with <span> so it can live inside
 * <p>/<h3>/<label> without invalid DOM nesting.
 */
const InfoTip: React.FC<InfoTipProps> = ({
  helpKey,
  children,
  className = "",
}) => {
  const [open, setOpen] = useState(false);
  const [below, setBelow] = useState(false);
  const rootRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocPointerDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onDocKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onDocPointerDown);
    document.addEventListener("keydown", onDocKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onDocPointerDown);
      document.removeEventListener("keydown", onDocKeyDown);
    };
  }, [open]);

  const entry = helpKey ? INDICATOR_HELP[helpKey] : undefined;
  // Non-breaking: unknown key with no override renders nothing.
  if (!entry && !children) return null;

  const show = () => {
    // Prefer above the trigger; flip below when too close to the viewport top.
    const rect = rootRef.current?.getBoundingClientRect();
    setBelow(!!rect && rect.top < 260);
    setOpen(true);
  };
  const toggle = () => (open ? setOpen(false) : show());

  const body = entry ? (
    <>
      <span className="block font-semibold text-ink text-[13px] mb-1">
        {entry.title}
      </span>
      <span className="block text-ink-secondary">{entry.what}</span>
      <span className="mt-1.5 flex flex-col gap-1">
        {entry.how.map((line, i) => (
          <span key={i} className="flex gap-1.5">
            <span className="text-ink-muted shrink-0">•</span>
            <span className="text-ink-secondary">{line}</span>
          </span>
        ))}
      </span>
      {entry.caution && (
        <span className="block mt-1.5 text-ink-muted italic">
          ⚠ {entry.caution}
        </span>
      )}
    </>
  ) : (
    children
  );

  return (
    <span
      ref={rootRef}
      className={`relative inline-flex ${className}`.trim()}
      onMouseEnter={show}
      onMouseLeave={() => setOpen(false)}
    >
      <span
        role="button"
        tabIndex={0}
        aria-label={entry ? `${entry.title} 설명` : "지표 설명"}
        aria-expanded={open}
        className="inline-flex items-center outline-none"
        onFocus={show}
        onBlur={() => setOpen(false)}
        onPointerDown={(e) => {
          // Never let the press reach parents (e.g. DataGrid header sort).
          e.stopPropagation();
          if (e.pointerType === "touch" || e.pointerType === "pen") {
            e.preventDefault(); // suppress synthesized mouse events
            toggle();
          }
        }}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            e.stopPropagation();
            toggle();
          }
        }}
      >
        <Info
          size={13}
          className="text-ink-muted hover:text-ink transition-colors cursor-help"
          aria-hidden
        />
      </span>
      {open && (
        <span
          role="tooltip"
          className={`absolute left-1/2 -translate-x-1/2 z-50 block ${
            below ? "top-full pt-1.5" : "bottom-full pb-1.5"
          }`}
          onClick={(e) => e.stopPropagation()}
        >
          <span className="block w-72 max-w-[80vw] bg-overlay border border-edge rounded-xl shadow-xl p-3.5 text-left text-xs leading-relaxed font-normal normal-case tracking-normal whitespace-normal cursor-auto">
            {body}
          </span>
        </span>
      )}
    </span>
  );
};

export default InfoTip;
