"use client";

import React, { useEffect, useState } from "react";
import { Pencil, Plus, Trash2, X } from "lucide-react";

import {
  StockHolding,
  useAddHoldingMutation,
  useRemoveHoldingMutation,
} from "@/state/api";

interface HoldingButtonProps {
  metaId: number;
  ticker: string;
  name?: string | null;
  /** iso_code ("KR"/"US"); drives the native currency. */
  isoCode: string;
  /** Existing position, or null when not held. */
  holding: StockHolding | null;
  className?: string;
}

const currencyFromIso = (iso: string): string =>
  iso === "KR" ? "KRW" : "USD";

/** Native-currency price/cost formatter (원 for KRW, $ for others). */
const fmtNative = (value: number, currency: string): string => {
  if (currency === "KRW") return `${Math.round(value).toLocaleString()}원`;
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

/** Fraction (0.12) → "+12.0%". */
const fmtPnlPct = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
};

/**
 * Shared holding-entry control for a single known stock.
 * Renders either a "보유 N주 · 평단 X · 손익 +Y%" chip (with edit/remove)
 * or a "+ 보유 추가" button that opens a small inline shares/avg_cost form.
 * Used on the stock detail page; self-contained (POST/DELETE + tag invalidation).
 */
const HoldingButton: React.FC<HoldingButtonProps> = ({
  metaId,
  isoCode,
  holding,
  className = "",
}) => {
  const [editing, setEditing] = useState(false);
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");

  const [addHolding, { isLoading: saving }] = useAddHoldingMutation();
  const [removeHolding, { isLoading: removing }] = useRemoveHoldingMutation();

  const currency = holding?.currency ?? currencyFromIso(isoCode);

  // Prefill the form whenever it opens (edit) or the holding changes.
  useEffect(() => {
    if (editing) {
      setShares(holding ? String(holding.shares) : "");
      setAvgCost(holding ? String(holding.avg_cost) : "");
    }
  }, [editing, holding]);

  const sharesNum = Number(shares);
  const avgCostNum = Number(avgCost);
  const valid =
    Number.isFinite(sharesNum) &&
    sharesNum > 0 &&
    Number.isFinite(avgCostNum) &&
    avgCostNum > 0;

  const handleSave = async () => {
    if (!valid || saving) return;
    await addHolding({
      meta_id: metaId,
      shares: sharesNum,
      avg_cost: avgCostNum,
      currency,
    }).unwrap();
    setEditing(false);
  };

  const handleRemove = async () => {
    if (removing) return;
    await removeHolding(metaId).unwrap();
  };

  if (editing) {
    return (
      <div
        className={`inline-flex flex-wrap items-end gap-2 p-2 rounded-xl bg-raised border border-edge ${className}`.trim()}
      >
        <div>
          <label className="block text-[10px] uppercase tracking-wider text-ink-muted mb-1">
            수량 (주)
          </label>
          <input
            type="number"
            min={0}
            step="any"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            placeholder="0"
            className="w-24 px-2.5 py-1.5 text-sm rounded-lg bg-surface border border-edge
                       text-ink num focus:outline-none focus:border-primary-400"
            aria-label="보유 수량"
          />
        </div>
        <div>
          <label className="block text-[10px] uppercase tracking-wider text-ink-muted mb-1">
            평단 ({currency})
          </label>
          <input
            type="number"
            min={0}
            step="any"
            value={avgCost}
            onChange={(e) => setAvgCost(e.target.value)}
            placeholder="0"
            className="w-28 px-2.5 py-1.5 text-sm rounded-lg bg-surface border border-edge
                       text-ink num focus:outline-none focus:border-primary-400"
            aria-label="평균 매입단가"
          />
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={!valid || saving}
          className="btn-primary px-3 py-1.5 text-sm"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          disabled={saving}
          aria-label="취소"
          className="p-2 rounded-lg text-ink-muted hover:text-ink hover:bg-overlay transition-colors"
        >
          <X size={16} aria-hidden />
        </button>
      </div>
    );
  }

  if (holding) {
    const pnlPct = holding.unrealized_pnl_pct;
    const pnlClass =
      pnlPct === null || pnlPct === undefined || pnlPct === 0
        ? "num text-ink-secondary"
        : pnlPct > 0
          ? "metric-positive"
          : "metric-negative";
    return (
      <div
        className={`inline-flex items-center gap-1.5 pl-3 pr-1.5 py-1 rounded-full bg-raised border border-edge ${className}`.trim()}
      >
        <span className="text-xs text-ink-secondary">
          보유 <span className="num text-ink font-medium">
            {holding.shares.toLocaleString()}
          </span>
          주 · 평단{" "}
          <span className="num text-ink">
            {fmtNative(holding.avg_cost, currency)}
          </span>
          {pnlPct !== null && pnlPct !== undefined && (
            <>
              {" · 손익 "}
              <span className={`text-xs ${pnlClass}`}>{fmtPnlPct(pnlPct)}</span>
            </>
          )}
        </span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          aria-label="보유 수정"
          className="p-1.5 rounded-full text-ink-muted hover:text-ink hover:bg-overlay transition-colors"
        >
          <Pencil size={13} aria-hidden />
        </button>
        <button
          type="button"
          onClick={handleRemove}
          disabled={removing}
          aria-label="보유 제거"
          className="p-1.5 rounded-full text-ink-muted hover:text-losses hover:bg-overlay transition-colors disabled:opacity-50"
        >
          <Trash2 size={13} aria-hidden />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                  rounded-lg bg-raised border border-edge text-ink-secondary
                  hover:bg-overlay hover:text-ink transition-colors ${className}`.trim()}
    >
      <Plus size={14} aria-hidden />
      보유 추가
    </button>
  );
};

export default HoldingButton;
