"use client";

import { X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { IpoPositionInput, IpoRow, useUpdateIpoPositionMutation } from "@/state/api";
import { apiErrorMessage, fmtDay, fmtWon } from "./format";

type FilledChoice = "auto" | "filled" | "unfilled";

interface IpoPositionModalProps {
  /** 입력할 공모주. null이면 닫혀 있다. */
  row: IpoRow | null;
  onClose: () => void;
}

const numberText = (v: number | null | undefined) =>
  typeof v === "number" && Number.isFinite(v) ? String(v) : "";

/** 실제 체결·매도 입력. 비우고 저장하면 그 항목은 배치 추정으로 돌아간다. */
export default function IpoPositionModal({ row, onClose }: IpoPositionModalProps) {
  if (!row) return null;
  // 종목이 바뀌면 폼을 새로 만들어 저장된 입력값으로 바로 채운다(빈 칸이 잠깐 보이지 않게).
  return <PositionForm key={row.event_id} row={row} onClose={onClose} />;
}

function PositionForm({ row, onClose }: { row: IpoRow; onClose: () => void }) {
  const [save, { isLoading: saving }] = useUpdateIpoPositionMutation();
  const titleId = useId();
  const fieldId = useId();
  const user = row.user ?? {};

  const [filled, setFilled] = useState<FilledChoice>(
    user.filled == null ? "auto" : user.filled ? "filled" : "unfilled"
  );
  const [entryPrice, setEntryPrice] = useState(numberText(user.entry_price));
  const [quantity, setQuantity] = useState(numberText(user.quantity));
  const [exitPrice, setExitPrice] = useState(numberText(user.exit_price));
  const [exitDate, setExitDate] = useState(user.exit_date ? user.exit_date.slice(0, 10) : "");
  const [note, setNote] = useState(user.note ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const listingDay = row.listing_date ? row.listing_date.slice(0, 10) : "";

  const submit = async (body: IpoPositionInput) => {
    setError(null);
    try {
      await save({ eventId: row.event_id, body }).unwrap();
      onClose();
    } catch (err) {
      setError(apiErrorMessage(err, "저장하지 못했습니다. 잠시 후 다시 시도하세요."));
    }
  };

  const handleSave = () => {
    const parsed: Record<"entry_price" | "quantity" | "exit_price", number | null> = {
      entry_price: null,
      quantity: null,
      exit_price: null,
    };
    const fields: [keyof typeof parsed, string, string][] = [
      ["entry_price", entryPrice, "체결가는"],
      ["quantity", quantity, "수량은"],
      ["exit_price", exitPrice, "매도가는"],
    ];
    for (const [key, raw, subject] of fields) {
      if (raw.trim() === "") continue;
      const value = Number(raw);
      if (!Number.isFinite(value) || value <= 0) {
        setError(`${subject} 0보다 큰 숫자로 입력하세요.`);
        return;
      }
      parsed[key] = value;
    }
    if (exitDate && listingDay && exitDate < listingDay) {
      setError("매도일이 상장일보다 이릅니다.");
      return;
    }
    submit({
      filled: filled === "auto" ? null : filled === "filled",
      ...parsed,
      exit_date: exitDate || null,
      note: note.trim() ? note.trim() : null,
    });
  };

  const handleClear = () =>
    submit({
      filled: null,
      entry_price: null,
      quantity: null,
      exit_price: null,
      exit_date: null,
      note: null,
    });

  const hasUserInput = row.user != null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="card relative max-h-[90vh] w-full max-w-lg overflow-y-auto"
      >
        <div className="mb-5 flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-ink">
              체결 입력 · {row.corp_name ?? row.event_id}
            </h2>
            <p className="num mt-1 text-xs text-ink-muted">
              상장 {fmtDay(row.listing_date)} · 주문 가격 {fmtWon(row.limit_price)}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="닫기"
            className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-raised hover:text-ink"
          >
            <X size={18} aria-hidden />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <span className="input-label">체결 여부</span>
            <div className="segmented-control" role="group" aria-label="체결 여부">
              {([
                ["auto", "추정 사용"],
                ["filled", "체결"],
                ["unfilled", "미체결"],
              ] as [FilledChoice, string][]).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={filled === value}
                  onClick={() => {
                    setFilled(value);
                    setError(null);
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor={`${fieldId}-entry`} className="input-label">
                체결가 (원)
              </label>
              <input
                id={`${fieldId}-entry`}
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={entryPrice}
                onChange={(e) => {
                  setEntryPrice(e.target.value);
                  setError(null);
                }}
                placeholder="비우면 추정값"
                className="input num"
              />
            </div>
            <div>
              <label htmlFor={`${fieldId}-qty`} className="input-label">
                수량 (주)
              </label>
              <input
                id={`${fieldId}-qty`}
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={quantity}
                onChange={(e) => {
                  setQuantity(e.target.value);
                  setError(null);
                }}
                placeholder="선택"
                className="input num"
              />
            </div>
            <div>
              <label htmlFor={`${fieldId}-exit`} className="input-label">
                매도가 (원)
              </label>
              <input
                id={`${fieldId}-exit`}
                type="number"
                inputMode="decimal"
                min={0}
                step="any"
                value={exitPrice}
                onChange={(e) => {
                  setExitPrice(e.target.value);
                  setError(null);
                }}
                placeholder="매도 후 입력"
                className="input num"
              />
            </div>
            <div>
              <label htmlFor={`${fieldId}-exit-date`} className="input-label">
                매도일
              </label>
              <input
                id={`${fieldId}-exit-date`}
                type="date"
                min={listingDay || undefined}
                value={exitDate}
                onChange={(e) => {
                  setExitDate(e.target.value);
                  setError(null);
                }}
                className="input num"
              />
            </div>
          </div>

          <div>
            <label htmlFor={`${fieldId}-note`} className="input-label">
              메모
            </label>
            <textarea
              id={`${fieldId}-note`}
              className="input min-h-20"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="체결 상황 등"
            />
          </div>

          <p className="text-xs leading-5 text-ink-muted">
            저장한 값은 바로 이 화면에 표시되고, 다음 저녁 배치부터 체결·매도·수익 계산에 반영됩니다.
            모든 칸을 비우고 저장하면 입력이 지워지고 추정값으로 돌아갑니다.
          </p>

          {error && (
            <p role="alert" className="text-danger text-xs">
              {error}
            </p>
          )}

          <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
            {hasUserInput && (
              <button
                type="button"
                onClick={handleClear}
                disabled={saving}
                className="btn-ghost mr-auto px-3 py-2 text-sm"
              >
                입력 지우기
              </button>
            )}
            <button type="button" onClick={onClose} className="btn-secondary px-4 py-2 text-sm">
              취소
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="btn-primary px-4 py-2 text-sm"
            >
              {saving ? "저장 중..." : "저장"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
