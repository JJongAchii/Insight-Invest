"use client";

import React, { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import Select, { SingleValue } from "react-select";

import {
  HoldingPosition,
  useAddHoldingMutation,
  useFetchMetaDataQuery,
} from "@/state/api";
import { tokenSelectStyles } from "@/components/ui/selectStyles";
import { MetaRow } from "@/app/stocksearch/types";

interface HoldingModalProps {
  open: boolean;
  onClose: () => void;
  /** When set, edit that position (ticker locked, fields pre-filled). */
  editing: HoldingPosition | null;
}

interface TickerOption {
  value: number;
  label: string;
  iso: string;
}

const currencyFromIso = (iso: string): string =>
  iso === "KR" ? "KRW" : "USD";

/** Add / edit a real holding. Search-picks a ticker (add) or locks it (edit). */
const HoldingModal: React.FC<HoldingModalProps> = ({
  open,
  onClose,
  editing,
}) => {
  const { data: rawMeta } = useFetchMetaDataQuery({}, { skip: !open });
  const [addHolding, { isLoading: saving }] = useAddHoldingMutation();

  const [selected, setSelected] = useState<TickerOption | null>(null);
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [error, setError] = useState<string | null>(null);

  const options = useMemo<TickerOption[]>(() => {
    const rows = (rawMeta as MetaRow[] | undefined) ?? [];
    return rows.map((r) => ({
      value: r.meta_id,
      label: `${r.ticker}${r.name ? ` · ${r.name}` : ""}`,
      iso: r.iso_code,
    }));
  }, [rawMeta]);

  // (Re)initialise whenever the modal opens or the edit target changes.
  useEffect(() => {
    if (!open) return;
    if (editing) {
      setSelected({
        value: editing.meta_id,
        label: `${editing.ticker}${editing.name ? ` · ${editing.name}` : ""}`,
        iso: editing.iso_code,
      });
      setShares(String(editing.shares));
      setAvgCost(String(editing.avg_cost));
    } else {
      setSelected(null);
      setShares("");
      setAvgCost("");
    }
    setError(null);
  }, [open, editing]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const currency = editing?.currency ?? currencyFromIso(selected?.iso ?? "US");

  const sharesNum = Number(shares);
  const avgCostNum = Number(avgCost);

  const handleSubmit = async () => {
    if (!selected) {
      setError("종목을 선택하세요");
      return;
    }
    if (!Number.isFinite(sharesNum) || sharesNum <= 0) {
      setError("수량을 올바르게 입력하세요");
      return;
    }
    if (!Number.isFinite(avgCostNum) || avgCostNum <= 0) {
      setError("평단을 올바르게 입력하세요");
      return;
    }
    try {
      await addHolding({
        meta_id: selected.value,
        shares: sharesNum,
        avg_cost: avgCostNum,
        currency,
      }).unwrap();
      onClose();
    } catch {
      setError("저장에 실패했습니다. 다시 시도하세요.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={editing ? "보유 종목 수정" : "보유 종목 추가"}
        className="relative w-full max-w-md card"
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-ink">
            {editing ? "보유 종목 수정" : "보유 종목 추가"}
          </h3>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-raised transition-colors"
          >
            <X size={18} aria-hidden />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="input-label">종목</label>
            {editing ? (
              <div className="px-4 py-2.5 rounded-xl bg-raised border border-edge text-ink text-sm">
                <span className="num font-medium">{editing.ticker}</span>
                {editing.name && (
                  <span className="ml-1.5 text-ink-muted">{editing.name}</span>
                )}
              </div>
            ) : (
              <Select<TickerOption>
                options={options}
                value={selected}
                onChange={(v: SingleValue<TickerOption>) => {
                  setSelected(v);
                  setError(null);
                }}
                placeholder="티커 또는 종목명 검색..."
                isClearable
                styles={tokenSelectStyles}
                noOptionsMessage={() => "결과 없음"}
              />
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="input-label">수량 (주)</label>
              <input
                type="number"
                min={0}
                step="any"
                value={shares}
                onChange={(e) => {
                  setShares(e.target.value);
                  setError(null);
                }}
                placeholder="0"
                className="input num"
                aria-label="보유 수량"
              />
            </div>
            <div>
              <label className="input-label">평단 ({currency})</label>
              <input
                type="number"
                min={0}
                step="any"
                value={avgCost}
                onChange={(e) => {
                  setAvgCost(e.target.value);
                  setError(null);
                }}
                placeholder="0"
                className="input num"
                aria-label="평균 매입단가"
              />
            </div>
          </div>

          {error && <p className="text-danger text-xs">{error}</p>}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary px-4 py-2 text-sm"
            >
              취소
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={saving}
              className="btn-primary px-4 py-2 text-sm"
            >
              {saving ? "저장 중..." : editing ? "수정" : "추가"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HoldingModal;
