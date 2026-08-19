"use client";

import React, { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import Select, { SingleValue } from "react-select";

import {
  HoldingPosition,
  useAddHoldingMutation,
  useFetchMetaDataQuery,
  useUpdateHoldingMetadataMutation,
} from "@/state/api";
import { tokenSelectStyles } from "@/components/ui/selectStyles";
import { MetaRow } from "@/app/stocksearch/types";

interface HoldingModalProps {
  open: boolean;
  onClose: () => void;
  /** When set, edit that position (ticker locked, fields pre-filled). */
  editing: HoldingPosition | null;
  ledgerStarted?: boolean;
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
  ledgerStarted = false,
}) => {
  const { data: rawMeta } = useFetchMetaDataQuery({}, { skip: !open });
  const [addHolding, { isLoading: saving }] = useAddHoldingMutation();
  const [updateMetadata, { isLoading: metadataSaving }] =
    useUpdateHoldingMetadataMutation();

  const [selected, setSelected] = useState<TickerOption | null>(null);
  const [shares, setShares] = useState("");
  const [avgCost, setAvgCost] = useState("");
  const [targetPct, setTargetPct] = useState("");
  const [thesis, setThesis] = useState("");
  const [invalidation, setInvalidation] = useState("");
  const [reviewDate, setReviewDate] = useState("");
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
      setTargetPct(
        editing.target_weight == null ? "" : String(editing.target_weight * 100)
      );
      setThesis(editing.thesis ?? "");
      setInvalidation(editing.invalidation ?? "");
      setReviewDate(editing.review_date ?? "");
    } else {
      setSelected(null);
      setShares("");
      setAvgCost("");
      setTargetPct("");
      setThesis("");
      setInvalidation("");
      setReviewDate("");
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
  const targetPctNum = targetPct.trim() === "" ? null : Number(targetPct);
  const targetValid =
    targetPctNum === null ||
    (Number.isFinite(targetPctNum) && targetPctNum >= 0 && targetPctNum <= 100);
  const canSubmit =
    selected !== null &&
    targetValid &&
    (ledgerStarted ||
      (Number.isFinite(sharesNum) && sharesNum > 0 && Number.isFinite(avgCostNum) && avgCostNum > 0));

  const handleSubmit = async () => {
    if (!selected) {
      setError("종목을 선택하세요");
      return;
    }
    if (!ledgerStarted && (!Number.isFinite(sharesNum) || sharesNum <= 0)) {
      setError("수량을 올바르게 입력하세요");
      return;
    }
    if (!ledgerStarted && (!Number.isFinite(avgCostNum) || avgCostNum <= 0)) {
      setError("평단을 올바르게 입력하세요");
      return;
    }
    if (
      targetPctNum !== null &&
      (!Number.isFinite(targetPctNum) || targetPctNum < 0 || targetPctNum > 100)
    ) {
      setError("목표 비중은 0~100%로 입력하세요");
      return;
    }
    try {
      if (ledgerStarted && editing) {
        await updateMetadata({
          meta_id: selected.value,
          target_weight: targetPctNum === null ? null : targetPctNum / 100,
          thesis,
          invalidation,
          review_date: reviewDate || null,
        }).unwrap();
      } else {
        await addHolding({
          meta_id: selected.value,
          shares: sharesNum,
          avg_cost: avgCostNum,
          currency,
          target_weight: targetPctNum === null ? null : targetPctNum / 100,
          thesis,
          invalidation,
          review_date: reviewDate || null,
        }).unwrap();
      }
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
        aria-label={editing ? "Edit Holding" : "Add Holding"}
        className="relative max-h-[90vh] w-full max-w-xl overflow-y-auto card"
      >
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-base font-semibold text-ink">
            {ledgerStarted && editing
              ? "Edit Holding Notes"
              : editing
                ? "Edit Holding"
                : "Add Holding"}
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

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <label>
              <span className="input-label">투자 논거</span>
              <textarea className="input min-h-20" value={thesis} onChange={(e) => setThesis(e.target.value)} placeholder="왜 보유하는가?" />
            </label>
            <label>
              <span className="input-label">무효화 조건</span>
              <textarea className="input min-h-20" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} placeholder="어떤 사실이면 매도·재검토할 것인가?" />
            </label>
          </div>

          <label className="block max-w-xs">
            <span className="input-label">다음 검토일</span>
            <input type="date" className="input" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} />
          </label>

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
                disabled={ledgerStarted}
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
                disabled={ledgerStarted}
              />
            </div>
          </div>

          {ledgerStarted && (
            <p className="text-xs text-ink-muted">
              수량과 평단은 불변 거래 원장에서 파생됩니다. 변경하려면 매수·매도 이벤트를 기록하세요.
            </p>
          )}

          <div>
            <label className="input-label">목표 비중 (%) · 선택</label>
            <input
              type="number"
              min={0}
              max={100}
              step="0.1"
              value={targetPct}
              onChange={(e) => {
                setTargetPct(e.target.value);
                setError(null);
              }}
              placeholder="투자자산 내 목표 비중"
              className="input num"
              aria-label="목표 비중"
            />
            <p className="text-[11px] text-ink-muted mt-1">
              현금은 포함하지 않습니다. 입력한 종목만 실제 비중과 괴리를 계산합니다.
            </p>
          </div>

          {error && <p className="text-danger text-xs">{error}</p>}
          {!canSubmit && (
            <p className="text-warning text-xs">
              종목과 0보다 큰 수량·평단을 입력하고 목표 비중 범위를 확인하세요.
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary px-4 py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={saving || metadataSaving || !canSubmit}
              className="btn-primary px-4 py-2 text-sm"
            >
              {saving || metadataSaving ? "저장 중..." : editing ? "Save Changes" : "Add Holding"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HoldingModal;
