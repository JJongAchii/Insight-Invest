"use client";

import { FormEvent, useEffect, useState } from "react";
import { X } from "lucide-react";

import { useUpdateWatchlistMutation, WatchlistItem } from "@/state/api";

export default function WatchlistThesisEditor({
  item,
  onClose,
}: {
  item: WatchlistItem;
  onClose: () => void;
}) {
  const [update, { isLoading, error }] = useUpdateWatchlistMutation();
  const [thesis, setThesis] = useState(item.thesis ?? "");
  const [catalyst, setCatalyst] = useState(item.catalyst ?? "");
  const [invalidation, setInvalidation] = useState(item.invalidation ?? "");
  const [reviewDate, setReviewDate] = useState(item.review_date ?? "");
  const [note, setNote] = useState(item.note ?? "");

  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [onClose]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await update({
      meta_id: item.meta_id,
      thesis,
      catalyst,
      invalidation,
      review_date: reviewDate || null,
      note,
    }).unwrap();
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4" role="presentation">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="watch-thesis-title"
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-edge bg-surface p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="watch-thesis-title" className="text-lg font-semibold text-ink">관심 논거 편집</h2>
            <p className="text-sm text-ink-muted">{item.name ?? item.ticker} · {item.ticker}</p>
          </div>
          <button type="button" onClick={onClose} aria-label="편집 닫기" className="p-2 text-ink-muted hover:text-ink">
            <X size={18} aria-hidden />
          </button>
        </div>

        <form onSubmit={submit} className="mt-5 space-y-4">
          <label className="block">
            <span className="input-label">관심 논거</span>
            <textarea className="input min-h-20" value={thesis} onChange={(e) => setThesis(e.target.value)} placeholder="왜 지금 관찰하는가?" />
          </label>
          <label className="block">
            <span className="input-label">예상 촉매</span>
            <textarea className="input min-h-16" value={catalyst} onChange={(e) => setCatalyst(e.target.value)} placeholder="실적, 정책, 수급 등 확인할 사건" />
          </label>
          <label className="block">
            <span className="input-label">반증·무효화 조건</span>
            <textarea className="input min-h-16" value={invalidation} onChange={(e) => setInvalidation(e.target.value)} placeholder="어떤 사실이 나오면 관점을 폐기할 것인가?" />
          </label>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="input-label">다음 검토일</span>
              <input type="date" className="input" value={reviewDate} onChange={(e) => setReviewDate(e.target.value)} />
            </label>
            <label className="block">
              <span className="input-label">기타 메모</span>
              <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
          </div>
          {error && <p className="text-sm text-losses">저장하지 못했습니다. 잠시 후 다시 시도해 주세요.</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={onClose}>취소</button>
            <button type="submit" className="btn-primary" disabled={isLoading}>{isLoading ? "저장 중..." : "논거 저장"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}
