"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { BookOpenCheck, CalendarClock } from "lucide-react";
import Link from "next/link";

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

  useEffect(() => {
    const raw = sessionStorage.getItem("ii-journal-prefill");
    if (!raw) return;
    try {
      const item = JSON.parse(raw);
      setForm({
        ...initialForm(),
        observation: [item.title, item.detail].filter(Boolean).join(" — "),
        invalidation: "",
        source_event_id: item.event_id,
        source_event: item,
      });
      setShowForm(true);
    } catch {
      // 손상된 로컬 초안은 버리고 일반 편집기를 유지한다.
    } finally {
      sessionStorage.removeItem("ii-journal-prefill");
    }
  }, []);

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
        eyebrow="Decision journal"
        title="판단 기록"
        description="판단 당시의 관찰과 해석을 분리하고, 반증·무효화 조건과 사후 검토일까지 함께 남깁니다."
        meta={
          <>
            <span>기록 {data?.items.length ?? 0}건</span>
            <span>·</span>
            <span>검토 기한 경과 {dueCount}건</span>
          </>
        }
        actions={<button className="btn-primary" onClick={() => setShowForm((value) => !value)}>{showForm ? "편집기 닫기" : "새 판단 기록"}</button>}
      />

      {dueCount > 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm text-ink">
          <CalendarClock size={18} aria-hidden /> 사후 검토일이 지난 판단이 {dueCount}개 있습니다.
        </div>
      )}

      {showForm && (
        <form onSubmit={submit} className="card relative space-y-0 overflow-hidden pt-6">
          <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" aria-hidden />
          <div className="pb-5">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary-300">Decision protocol</p>
            <h2 className="mt-2 text-lg font-semibold text-ink">사실에서 검증 조건까지 순서대로 기록합니다</h2>
          </div>

          <section className="border-t border-edge py-5" aria-labelledby="journal-step-observation">
            <div className="grid gap-4 lg:grid-cols-[9rem_minmax(0,1fr)]">
              <div>
                <p className="font-mono text-[10px] text-primary-300">01</p>
                <h3 id="journal-step-observation" className="mt-1 font-semibold text-ink">사실과 범위</h3>
                <p className="mt-1 text-xs leading-5 text-ink-muted">해석 전에 관찰과 시간축을 고정합니다.</p>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <label className="block lg:col-span-2">
                  <span className="input-label">관찰한 사실</span>
                  <textarea required className="input min-h-24" value={form.observation} onChange={(e) => setForm({ ...form, observation: e.target.value })} placeholder="해석을 섞지 않은 데이터·사건" />
                </label>
                <div className="grid grid-cols-2 gap-3 lg:grid-cols-1">
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
            </div>
          </section>

          <section className="border-t border-edge py-5" aria-labelledby="journal-step-decision">
            <div className="grid gap-4 lg:grid-cols-[9rem_minmax(0,1fr)]">
              <div>
                <p className="font-mono text-[10px] text-primary-300">02</p>
                <h3 id="journal-step-decision" className="mt-1 font-semibold text-ink">해석과 결정</h3>
                <p className="mt-1 text-xs leading-5 text-ink-muted">의미와 실제 행동을 분리해 적습니다.</p>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <label className="block">
                  <span className="input-label">해석</span>
                  <textarea required className="input min-h-24" value={form.interpretation} onChange={(e) => setForm({ ...form, interpretation: e.target.value })} placeholder="그 사실이 내게 무엇을 의미하는가?" />
                </label>
                <label className="block">
                  <span className="input-label">결정</span>
                  <textarea required className="input min-h-24" value={form.decision} onChange={(e) => setForm({ ...form, decision: e.target.value })} placeholder="실행·보류·관찰 중 무엇을 할 것인가?" />
                </label>
              </div>
            </div>
          </section>

          <section className="border-y border-edge py-5" aria-labelledby="journal-step-review">
            <div className="grid gap-4 lg:grid-cols-[9rem_minmax(0,1fr)]">
              <div>
                <p className="font-mono text-[10px] text-primary-300">03</p>
                <h3 id="journal-step-review" className="mt-1 font-semibold text-ink">반증 계획</h3>
                <p className="mt-1 text-xs leading-5 text-ink-muted">틀렸음을 인정할 조건과 날짜를 정합니다.</p>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <label>
                  <span className="input-label">반대 근거</span>
                  <textarea className="input min-h-24" value={form.counter_evidence} onChange={(e) => setForm({ ...form, counter_evidence: e.target.value })} placeholder="현재 판단과 반대되는 데이터" />
                </label>
                <label>
                  <span className="input-label">무효화 조건</span>
                  <textarea className="input min-h-24" value={form.invalidation} onChange={(e) => setForm({ ...form, invalidation: e.target.value })} placeholder="판단을 철회하거나 수정할 구체적 조건" />
                </label>
                <label className="block max-w-xs">
                  <span className="input-label">사후 검토일</span>
                  <input required type="date" className="input" value={form.review_date} onChange={(e) => setForm({ ...form, review_date: e.target.value })} />
                </label>
              </div>
            </div>
          </section>

          <div className="flex flex-col gap-3 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs leading-5 text-ink-muted">저장 시점의 시간축별 근거·충돌·데이터 상태가 자동으로 함께 고정됩니다.</p>
            <div className="shrink-0">
              {createError && <p className="mb-2 text-sm text-losses">판단을 저장하지 못했습니다.</p>}
              <button className="btn-primary w-full sm:w-auto" disabled={isCreating}>{isCreating ? "근거 스냅샷 저장 중..." : "판단과 근거 저장"}</button>
            </div>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="card"><LoadingState label="판단 기록을 불러오는 중..." /></div>
      ) : !data?.items.length ? (
        <div className="card"><EmptyState icon={<BookOpenCheck size={28} aria-hidden />} title="아직 기록한 판단이 없습니다" hint="시장 전망보다 검증 가능한 무효화 조건을 먼저 적어 보세요." /></div>
      ) : (
        <div className="space-y-4">
          {data.items.map((entry) => (
            <article id={`entry-${entry.entry_id}`} key={entry.entry_id} className="card scroll-mt-24">
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
                  {entry.evidence_snapshot.source_event?.title && (
                    <p className="mb-2 text-ink-secondary">
                      Source: {entry.evidence_snapshot.source_event.link ? (
                        <Link href={entry.evidence_snapshot.source_event.link} className="text-primary-400 hover:underline">
                          {entry.evidence_snapshot.source_event.title}
                        </Link>
                      ) : entry.evidence_snapshot.source_event.title}
                    </p>
                  )}
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
