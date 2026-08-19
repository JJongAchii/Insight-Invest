"use client";

import { FormEvent, useMemo, useState } from "react";
import { BookOpenCheck, CalendarClock } from "lucide-react";

import PageHeader from "@/components/ui/PageHeader";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import {
  CreateJournalPayload,
  DecisionHorizon,
  JournalEntry,
  useCreateJournalMutation,
  useFetchJournalQuery,
  useReviewJournalMutation,
} from "@/state/api";
import { formatDate } from "@/lib/market";

const HORIZON_LABEL: Record<DecisionHorizon, string> = {
  intraday: "장중 · 당일",
  tactical: "전술 · 1~4주",
  structural: "구조적 · 3~12개월",
};

const futureDate = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
};

const initialForm = (): CreateJournalPayload => ({
  observation: "",
  interpretation: "",
  decision: "",
  horizon: "tactical",
  confidence: 3,
  counter_evidence: "",
  invalidation: "",
  review_date: futureDate(14),
});

function ReviewForm({ entry }: { entry: JournalEntry }) {
  const [outcome, setOutcome] = useState("");
  const [lesson, setLesson] = useState("");
  const [review, { isLoading, error }] = useReviewJournalMutation();

  if (entry.reviewed_at) {
    return (
      <div className="mt-4 rounded-xl border border-edge bg-raised p-3">
        <p className="text-xs font-semibold text-ink-secondary">사후 검토 · {formatDate(entry.reviewed_at)}</p>
        <p className="mt-1 text-sm text-ink">{entry.outcome}</p>
        {entry.lesson && <p className="mt-1 text-sm text-ink-secondary">배운 점: {entry.lesson}</p>}
      </div>
    );
  }

  return (
    <details className="mt-4 rounded-xl border border-edge p-3">
      <summary className="cursor-pointer text-sm font-medium text-ink">결과를 사후 검토하기</summary>
      <form
        className="mt-3 space-y-3"
        onSubmit={async (event) => {
          event.preventDefault();
          await review({ entry_id: entry.entry_id, outcome, lesson }).unwrap();
        }}
      >
        <textarea required className="input min-h-16" value={outcome} onChange={(e) => setOutcome(e.target.value)} placeholder="실제로 무엇이 일어났는가?" />
        <textarea className="input min-h-16" value={lesson} onChange={(e) => setLesson(e.target.value)} placeholder="다음 판단에 반영할 점" />
        {error && <p className="text-sm text-losses">검토를 저장하지 못했습니다.</p>}
        <button className="btn-secondary" disabled={isLoading}>{isLoading ? "저장 중..." : "사후 검토 저장"}</button>
      </form>
    </details>
  );
}

export default function JournalPage() {
  const { data, isLoading } = useFetchJournalQuery();
  const [create, { isLoading: isCreating, error: createError }] = useCreateJournalMutation();
  const [form, setForm] = useState<CreateJournalPayload>(initialForm);
  const [showForm, setShowForm] = useState(false);

  const dueCount = useMemo(
    () => (data?.items ?? []).filter((item) => !item.reviewed_at && item.review_date <= new Date().toISOString().slice(0, 10)).length,
    [data]
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await create(form).unwrap();
    setForm(initialForm());
    setShowForm(false);
  };

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="Decision Journal"
        description="판단 당시의 관찰·반증·무효화 조건과 데이터 기준일을 함께 남깁니다"
        actions={<button className="btn-primary" onClick={() => setShowForm((value) => !value)}>{showForm ? "Close Editor" : "New Decision"}</button>}
      />

      {dueCount > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-ink">
          <CalendarClock size={18} aria-hidden /> 사후 검토일이 지난 판단이 {dueCount}개 있습니다.
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="card space-y-5">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <label className="block lg:col-span-2">
              <span className="input-label">관찰한 사실</span>
              <textarea required className="input min-h-20" value={form.observation} onChange={(e) => setForm({ ...form, observation: e.target.value })} placeholder="해석을 섞지 않은 데이터·사건" />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label>
                <span className="input-label">시간축</span>
                <select className="input" value={form.horizon} onChange={(e) => setForm({ ...form, horizon: e.target.value as DecisionHorizon })}>
                  {Object.entries(HORIZON_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>
                <span className="input-label">확신도 1~5</span>
                <input type="number" className="input" min={1} max={5} value={form.confidence} onChange={(e) => setForm({ ...form, confidence: Number(e.target.value) })} />
              </label>
            </div>
          </div>
          <label className="block">
            <span className="input-label">해석</span>
            <textarea required className="input min-h-20" value={form.interpretation} onChange={(e) => setForm({ ...form, interpretation: e.target.value })} placeholder="그 사실이 내게 무엇을 의미하는가?" />
          </label>
          <label className="block">
            <span className="input-label">결정</span>
            <textarea required className="input min-h-20" value={form.decision} onChange={(e) => setForm({ ...form, decision: e.target.value })} placeholder="실행·보류·관찰 중 무엇을 할 것인가?" />
          </label>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <label>
              <span className="input-label">반대 근거</span>
              <textarea className="input min-h-20" value={form.counter_evidence} onChange={(e) => setForm({ ...form, counter_evidence: e.target.value })} />
            </label>
            <label>
              <span className="input-label">무효화 조건</span>
              <textarea className="input min-h-20" value={form.invalidation} onChange={(e) => setForm({ ...form, invalidation: e.target.value })} />
            </label>
          </div>
          <label className="block max-w-xs">
            <span className="input-label">사후 검토일</span>
            <input required type="date" className="input" value={form.review_date} onChange={(e) => setForm({ ...form, review_date: e.target.value })} />
          </label>
          <p className="text-xs text-ink-muted">저장 시점의 시간축별 근거·충돌·데이터 상태가 자동으로 함께 고정됩니다.</p>
          {createError && <p className="text-sm text-losses">판단을 저장하지 못했습니다.</p>}
          <button className="btn-primary" disabled={isCreating}>{isCreating ? "근거 스냅샷 저장 중..." : "판단과 근거 저장"}</button>
        </form>
      )}

      {isLoading ? (
        <div className="card"><LoadingState label="판단 기록을 불러오는 중..." /></div>
      ) : !data?.items.length ? (
        <div className="card"><EmptyState icon={<BookOpenCheck size={28} aria-hidden />} title="아직 기록한 판단이 없습니다" hint="시장 전망보다 검증 가능한 무효화 조건을 먼저 적어 보세요." /></div>
      ) : (
        <div className="space-y-4">
          {data.items.map((entry) => (
            <article key={entry.entry_id} className="card">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span className="badge-neutral">{HORIZON_LABEL[entry.horizon]}</span>
                  <h2 className="mt-2 text-lg font-semibold text-ink">{entry.decision}</h2>
                </div>
                <div className="text-right text-xs text-ink-muted">
                  <p>작성 {formatDate(entry.created_at)}</p>
                  <p>검토 {formatDate(entry.review_date)} · 확신도 {entry.confidence}/5</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                <div className="rounded-xl bg-raised p-3"><p className="text-xs font-semibold text-ink-secondary">관찰</p><p className="mt-1 text-sm text-ink">{entry.observation}</p></div>
                <div className="rounded-xl bg-raised p-3"><p className="text-xs font-semibold text-ink-secondary">해석</p><p className="mt-1 text-sm text-ink">{entry.interpretation}</p></div>
                <div className="rounded-xl bg-raised p-3"><p className="text-xs font-semibold text-ink-secondary">반대 근거</p><p className="mt-1 text-sm text-ink">{entry.counter_evidence || "기록 없음"}</p></div>
                <div className="rounded-xl bg-raised p-3"><p className="text-xs font-semibold text-ink-secondary">무효화 조건</p><p className="mt-1 text-sm text-ink">{entry.invalidation || "기록 없음"}</p></div>
              </div>
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer text-ink-secondary">작성 당시 데이터 스냅샷</summary>
                <div className="mt-2 rounded-xl border border-edge p-3 text-xs text-ink-muted">
                  <p>{entry.evidence_snapshot.tone_label ?? "종합 문구 없음"}</p>
                  <p>계산 {formatDate(entry.evidence_snapshot.generated_at)}</p>
                  <p>{entry.evidence_snapshot.method}</p>
                </div>
              </details>
              <ReviewForm entry={entry} />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
