"use client";

import {
  Archive,
  Bookmark,
  BookOpen,
  Check,
  CheckCheck,
  CheckCircle2,
  Clock3,
  ExternalLink,
  LibraryBig,
  RefreshCw,
  Radar,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import ResearchBrief from "./ResearchBrief";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  ResearchEntry,
  ResearchEvidenceDimension,
  ResearchLane,
  ResearchView,
  useAcknowledgeResearchSeenMutation,
  useFetchResearchQuery,
  useMarkAllResearchReadMutation,
  useUpdateResearchReadStateMutation,
  useUpdateResearchSavedStateMutation,
} from "@/state/api";

const VIEW_OPTIONS = [
  { value: "all", label: "전체", icon: LibraryBig },
  { value: "unread", label: "안 읽음", icon: BookOpen },
  { value: "read", label: "읽음", icon: CheckCircle2 },
  { value: "saved", label: "보관함", icon: Bookmark },
] as const;

const LANE_OPTIONS = [
  {
    value: "core",
    label: "핵심 연구",
    description: "공식 원문에서 읽을 수 있는 퀀트 아이디어·분석·논문",
    icon: Sparkles,
  },
  {
    value: "discovery",
    label: "발견함",
    description: "초록·연구 모음과 한국어 분석을 기다리는 자료",
    icon: Radar,
  },
  {
    value: "updates",
    label: "데이터·도구",
    description: "데이터 수정, 코드 이슈와 구현 변경 기록",
    icon: RefreshCw,
  },
  {
    value: "all",
    label: "전체 기록",
    description: "알림에서 제외된 기존 피드와 맥락 자료까지 보존",
    icon: Archive,
  },
] as const;

const PROVENANCE_LABELS = {
  release_detail: "릴리스 상세",
  full_body: "전체 본문",
  full_article: "공개 본문",
  full_pdf: "공개 PDF",
  pdf_excerpt: "PDF 일부 추출",
  abstract: "초록만 확보",
} as const;

const TYPE_LABELS = {
  research_article: "연구 글",
  research_paper: "논문·연구보고서",
  preprint: "프리프린트 · 미검증",
  research_digest: "연구 모음",
  evidence_update: "데이터·도구 업데이트",
} as const;

const EVIDENCE_LABELS: Record<ResearchEvidenceDimension, string> = {
  method: "방법",
  data: "데이터",
  validation: "검증",
  result: "결과",
};

const parseView = (value: string | null): ResearchView => {
  if (VIEW_OPTIONS.some((option) => option.value === value)) return value as ResearchView;
  return "all";
};

const parseLane = (value: string | null): ResearchLane => {
  if (LANE_OPTIONS.some((option) => option.value === value)) return value as ResearchLane;
  return "core";
};

const formatDate = (value: string) => {
  if (!value) return "날짜 미상";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
};

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
};

const replaceLibraryUrl = (
  sourceId: string,
  view: ResearchView,
  query: string,
  lane: ResearchLane,
) => {
  const url = new URL(window.location.href);
  if (sourceId) url.searchParams.set("source", sourceId);
  else url.searchParams.delete("source");
  if (view !== "all") url.searchParams.set("view", view);
  else url.searchParams.delete("view");
  if (query) url.searchParams.set("q", query);
  else url.searchParams.delete("q");
  if (lane !== "core") url.searchParams.set("lane", lane);
  else url.searchParams.delete("lane");
  url.searchParams.delete("filter");
  url.searchParams.delete("entry");
  window.history.replaceState(window.history.state, "", url);
};

function ResearchCard({
  item,
  selected,
  onError,
}: {
  item: ResearchEntry;
  selected: boolean;
  onError: (message: string) => void;
}) {
  const [updateReadState, { isLoading: isUpdatingRead }] =
    useUpdateResearchReadStateMutation();
  const [updateSavedState, { isLoading: isUpdatingSaved }] =
    useUpdateResearchSavedStateMutation();
  const authors = item.authors.filter(Boolean).join(", ");
  const laneLabel =
    item.research_lane === "core"
      ? "핵심"
      : item.research_lane === "discovery"
        ? "발견"
        : item.research_lane === "updates" ? "업데이트" : "기록";
  const relevance = item.relevance_terms.slice(0, 2).join(" · ");
  const schemaThreeEvidence =
    item.record_schema_version === 3 && item.item_type === "evidence_update";

  const toggleRead = async () => {
    try {
      await updateReadState({ entryId: item.entry_id, read: !item.is_read }).unwrap();
    } catch {
      onError("읽음 상태를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    }
  };

  const toggleSaved = async () => {
    try {
      await updateSavedState({ entryId: item.entry_id, saved: !item.is_saved }).unwrap();
    } catch {
      onError("보관 상태를 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.");
    }
  };

  const markReadOnOpen = () => {
    if (!item.is_read) {
      void updateReadState({ entryId: item.entry_id, read: true })
        .unwrap()
        .catch(() => onError("원문은 열었지만 읽음 상태를 저장하지 못했습니다."));
    }
  };

  return (
    <article
      id={`research-${item.entry_id}`}
      className={`relative scroll-mt-24 p-4 transition-colors sm:p-5 ${
        selected ? "bg-primary-500/10 shadow-[inset_2px_0_0_var(--primary)]" : "hover:bg-raised/35"
      }`}
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-2 h-2.5 w-2.5 shrink-0 rounded-full ${
            item.is_read ? "bg-ink-muted/40" : "bg-primary-400"
          }`}
          aria-label={item.is_read ? "읽음" : "읽지 않음"}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span className="badge-neutral">{item.source_name}</span>
            <span
              title={relevance || undefined}
              className={`rounded-full px-2 py-0.5 font-medium ${
                item.research_lane === "core"
                  ? "bg-emerald-500/15 text-emerald-300"
                  : item.research_lane === "discovery"
                    ? "bg-sky-500/15 text-sky-300"
                    : "bg-surface-raised text-ink-muted"
              }`}
            >
              {laneLabel}
              {relevance ? ` · ${relevance}` : ""}
            </span>
            {schemaThreeEvidence && (
              <>
                <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-2 py-0.5 font-medium text-amber-200">
                  근거 업데이트
                </span>
                {item.content_provenance && (
                  <span className="rounded-full border border-violet-400/25 bg-violet-400/10 px-2 py-0.5 font-medium text-violet-200">
                    {PROVENANCE_LABELS[item.content_provenance]}
                  </span>
                )}
                {item.evidence_dimensions?.map((dimension) => (
                  <span
                    key={dimension}
                    className="rounded-full border border-edge bg-raised/70 px-2 py-0.5 font-medium text-ink-secondary"
                    title={item.evidence_excerpts?.[dimension]?.join("\n")}
                  >
                    근거 · {EVIDENCE_LABELS[dimension]}
                  </span>
                ))}
              </>
            )}
            {item.record_schema_version === 4 && (
              <>
                {item.item_type && <span className="badge-neutral">{TYPE_LABELS[item.item_type]}</span>}
                {item.content_provenance && <span>{PROVENANCE_LABELS[item.content_provenance]}</span>}
              </>
            )}
            {!item.is_read && (
              <span className="rounded-full bg-primary-500/15 px-2 py-0.5 font-medium text-primary-400">
                새 자료
              </span>
            )}
            {item.is_saved && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary-500/15 px-2 py-0.5 font-medium text-primary-300">
                <Bookmark size={11} fill="currentColor" aria-hidden /> 보관됨
              </span>
            )}
            <span className="inline-flex items-center gap-1 sm:ml-auto">
              <Clock3 size={13} aria-hidden />
              {item.date_precision === "month" ? `${item.published_at.slice(0, 7)} 발행호` : formatDate(item.published_at || item.discovered_at)}
            </span>
          </div>

          <h2 className="mt-2 text-base font-semibold leading-6 text-ink sm:text-lg">
            {item.analysis?.brief.title_ko || item.title}
          </h2>
          {item.analysis && <p className="mt-1 text-xs leading-5 text-ink-muted" lang="en">{item.title}</p>}
          {authors && <p className="mt-1 text-xs text-ink-muted">{authors}</p>}
          <ResearchBrief item={item} />

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary-500/15 px-3 py-2 text-xs font-semibold text-primary-300 transition-colors hover:bg-primary-500/25"
              onClick={markReadOnOpen}
            >
              원문 열기 <ExternalLink size={15} aria-hidden />
            </a>
            {item.pdf_url && item.pdf_url !== item.url && (
              <a href={item.pdf_url} target="_blank" rel="noopener noreferrer" onClick={markReadOnOpen}
                className="inline-flex items-center gap-1.5 rounded-lg border border-edge px-3 py-2 text-xs font-semibold text-ink-secondary hover:bg-raised">
                PDF 열기 <ExternalLink size={15} aria-hidden />
              </a>
            )}
            <button
              type="button"
              className="btn-ghost inline-flex items-center gap-1.5 px-3 py-2 text-xs"
              onClick={() => void toggleRead()}
              disabled={isUpdatingRead}
            >
              {item.is_read ? <BookOpen size={15} /> : <Check size={15} />}
              {item.is_read ? "안 읽음으로" : "읽음 표시"}
            </button>
            <button
              type="button"
              aria-pressed={item.is_saved}
              className={`btn-ghost inline-flex items-center gap-1.5 px-3 py-2 text-xs ${
                item.is_saved ? "text-primary-300" : ""
              }`}
              onClick={() => void toggleSaved()}
              disabled={isUpdatingSaved}
            >
              <Bookmark size={15} fill={item.is_saved ? "currentColor" : "none"} />
              {item.is_saved ? "보관 해제" : "보관"}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export default function ResearchPage() {
  const [sourceId, setSourceId] = useState("");
  const [view, setView] = useState<ResearchView>("all");
  const [lane, setLane] = useState<ResearchLane>("core");
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [entryId, setEntryId] = useState("");
  const [initialized, setInitialized] = useState(false);
  const [notice, setNotice] = useState<{ kind: "success" | "error"; message: string } | null>(
    null,
  );
  const [markAllRead, { isLoading: isMarkingAllRead }] = useMarkAllResearchReadMutation();
  const [acknowledgeResearchSeen] = useAcknowledgeResearchSeenMutation();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialView = params.get("filter") === "unread" ? "unread" : parseView(params.get("view"));
    const initialQuery = params.get("q")?.trim() ?? "";
    setSourceId(params.get("source") ?? "");
    setView(initialView);
    setLane(parseLane(params.get("lane")));
    setSearchInput(initialQuery);
    setQuery(initialQuery);
    setEntryId(params.get("entry") ?? "");
    setInitialized(true);
  }, []);

  useEffect(() => {
    if (!initialized) return;
    if (searchInput.trim() === query) return;
    const timer = window.setTimeout(() => {
      const nextQuery = searchInput.trim();
      setQuery(nextQuery);
      setEntryId("");
      const url = new URL(window.location.href);
      if (nextQuery) url.searchParams.set("q", nextQuery);
      else url.searchParams.delete("q");
      url.searchParams.delete("entry");
      window.history.replaceState(window.history.state, "", url);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [initialized, query, searchInput]);

  const { data, isLoading, error, refetch, isFetching } = useFetchResearchQuery(
    {
      sourceId: sourceId || undefined,
      view,
      lane,
      query: query || undefined,
      entryId: entryId || undefined,
      limit: 500,
    },
    {
      skip: !initialized,
      pollingInterval: 60_000,
      refetchOnFocus: true,
      refetchOnReconnect: true,
    },
  );

  useEffect(() => {
    if (!entryId || !data?.items.length) return;
    document.getElementById(`research-${entryId}`)?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  }, [data, entryId]);

  useEffect(() => {
    const nav = navigator as Navigator & { clearAppBadge?: () => Promise<void> };
    if (data && nav.clearAppBadge) {
      nav.clearAppBadge().catch(() => undefined);
    }
  }, [data]);

  useEffect(() => {
    if (!data?.generated_at) return;
    void acknowledgeResearchSeen({ through: data.generated_at });
  }, [acknowledgeResearchSeen, data?.generated_at]);

  const selectSource = (value: string) => {
    setSourceId(value);
    setEntryId("");
    replaceLibraryUrl(value, view, query, lane);
  };

  const selectView = (value: ResearchView) => {
    setView(value);
    setEntryId("");
    replaceLibraryUrl(sourceId, value, query, lane);
  };

  const selectLane = (value: ResearchLane) => {
    setLane(value);
    setSourceId("");
    setEntryId("");
    replaceLibraryUrl("", view, query, value);
  };

  const clearSearch = () => {
    setSearchInput("");
    setQuery("");
    setEntryId("");
    replaceLibraryUrl(sourceId, view, "", lane);
  };

  const markEverythingRead = async () => {
    const unread = data?.unread ?? 0;
    if (!unread) return;
    if (!window.confirm(`읽지 않은 자료 ${unread}건을 모두 읽음으로 표시할까요?`)) return;
    try {
      const result = await markAllRead({ lane }).unwrap();
      setView("all");
      setEntryId("");
      replaceLibraryUrl(sourceId, "all", query, lane);
      setNotice({
        kind: "success",
        message: `${result.updated}건을 읽음으로 표시했습니다. 자료는 읽음과 전체 기록에서 계속 볼 수 있습니다.`,
      });
    } catch {
      setNotice({
        kind: "error",
        message: "모두 읽음 처리를 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      });
    }
  };

  const counts: Record<ResearchView, number> = {
    all: (data?.unread ?? 0) + (data?.read ?? 0),
    unread: data?.unread ?? 0,
    read: data?.read ?? 0,
    saved: data?.saved ?? 0,
  };

  const emptyTitle = query
    ? `“${query}” 검색 결과가 없습니다`
    : view === "saved"
      ? "보관한 자료가 없습니다"
      : view === "read"
        ? "읽은 자료가 없습니다"
        : view === "unread"
          ? "읽지 않은 자료가 없습니다"
          : "조건에 맞는 자료가 없습니다";

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        eyebrow="Research library"
        title="리서치"
        description="퀀트 기관과 연구자의 공식 원문을 모아 읽고, 아이디어를 발견하고, 내 서재에 보관하세요."
        meta={
          <>
            <span>안 읽음 {data?.unread ?? 0}</span>
            <span>·</span>
            <span>{data?.generated_at ? `마지막 반영 ${formatDateTime(data.generated_at)}` : "피드 확인 중"}</span>
          </>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1.5"
              onClick={() => void markEverythingRead()}
              disabled={!data?.unread || isMarkingAllRead}
            >
              <CheckCheck size={15} />
              {isMarkingAllRead ? "처리 중…" : "모두 읽음"}
            </button>
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1.5"
              onClick={() => refetch()}
              disabled={!initialized || isFetching}
            >
              <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} />
              새로고침
            </button>
          </div>
        }
      />

      {notice && (
        <div
          role={notice.kind === "error" ? "alert" : "status"}
          className={`flex items-start justify-between gap-3 rounded-xl border px-4 py-3 text-sm ${
            notice.kind === "error"
              ? "border-red-500/30 bg-red-500/10 text-red-300"
              : "border-primary-500/30 bg-primary-500/10 text-primary-300"
          }`}
        >
          <span>{notice.message}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="알림 닫기">
            <X size={16} />
          </button>
        </div>
      )}

      {entryId && (
        <div className="rounded-xl border border-primary-500/30 bg-primary-500/10 px-4 py-3 text-sm text-primary-300">
          알림에서 선택한 자료를 표시하고 있습니다. 읽은 뒤에도 전체·읽음·보관함에서 다시 찾을
          수 있습니다.
        </div>
      )}

      <section className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4" aria-label="리서치 자료 유형">
        {LANE_OPTIONS.map((option) => {
          const Icon = option.icon;
          const active = lane === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={active}
              onClick={() => selectLane(option.value)}
              className={`rounded-2xl border p-4 text-left transition-colors ${
                active
                  ? "border-primary-500 bg-primary-500/15"
                  : "border-edge bg-surface hover:border-primary-500/40"
              }`}
            >
              <span className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
                  <Icon size={17} className={active ? "text-primary-300" : "text-ink-muted"} />
                  {option.label}
                </span>
                <span className="num text-sm text-ink-muted">
                  {data?.lane_counts[option.value] ?? 0}
                </span>
              </span>
              <span className="mt-2 block text-xs leading-5 text-ink-muted">
                {option.description}
              </span>
            </button>
          );
        })}
      </section>

      <p className="-mt-3 px-1 text-xs leading-5 text-ink-muted">
        사이드바 배지와 iPhone 알림은 새 핵심 연구에 표시됩니다.
        초록·연구 모음·데이터 업데이트는 별도로 보존하며, 초기 자료 채우기와 요약 수정은 다시 알리지 않습니다.
      </p>

      <div className="grid gap-5 xl:grid-cols-[15rem_minmax(0,1fr)] xl:items-start">
        <aside className="rounded-2xl border border-edge bg-surface p-4 xl:sticky xl:top-28">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary-300">Library view</p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-1" aria-label="리서치 보기 방식">
            {VIEW_OPTIONS.map((option) => {
              const Icon = option.icon;
              const active = view === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => selectView(option.value)}
                  className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-sm transition-colors ${
                    active
                      ? "border-primary-500/60 bg-primary-500/15 text-primary-300"
                      : "border-transparent text-ink-secondary hover:border-edge hover:bg-raised hover:text-ink"
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <Icon size={16} aria-hidden /> {option.label}
                  </span>
                  <span className="num text-xs">{counts[option.value]}</span>
                </button>
              );
            })}
          </div>

          <div className="mt-4 border-t border-edge pt-4">
            <label className="block text-xs font-medium text-ink-muted">
              출처
              <select
                value={sourceId}
                onChange={(event) => selectSource(event.target.value)}
                className="input mt-1.5 w-full"
              >
                <option value="">모든 출처</option>
                {data?.sources.map((source) => (
                  <option key={source.source_id} value={source.source_id}>
                    {source.source_name} ({source.count})
                  </option>
                ))}
              </select>
            </label>
            <p className="mt-3 text-xs leading-5 text-ink-muted">
              읽음은 삭제가 아닙니다. 다시 사용할 자료는 보관함에 따로 남길 수 있습니다.
            </p>
          </div>
        </aside>

        <section className="min-w-0 space-y-4" aria-labelledby="research-results-title">
          <div className="rounded-2xl border border-edge bg-surface p-3">
            <label className="relative block">
              <span className="sr-only">리서치 검색</span>
              <Search
                size={18}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
                aria-hidden
              />
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                className="input w-full border-transparent bg-raised/70 pl-10 pr-10"
                placeholder="제목, 요약, 저자, 출처 검색"
                maxLength={200}
              />
              {searchInput && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted hover:text-ink"
                  aria-label="검색어 지우기"
                >
                  <X size={17} />
                </button>
              )}
            </label>
          </div>

          <div className="flex items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">Reading queue</p>
              <h2 id="research-results-title" className="mt-1 text-base font-semibold text-ink">
                {VIEW_OPTIONS.find((option) => option.value === view)?.label ?? "전체"} 자료
              </h2>
            </div>
            <p className="text-xs text-ink-muted">
              결과 <strong className="num font-semibold text-ink">{data?.total ?? 0}</strong>건
            </p>
          </div>

          {error ? (
            <div className="card">
              <ErrorState message="리서치 서재를 불러오지 못했습니다." onRetry={refetch} />
            </div>
          ) : isLoading || !initialized ? (
            <div className="card">
              <LoadingState label="리서치 서재를 불러오는 중..." />
            </div>
          ) : !data?.items.length ? (
            <div className="card">
              <EmptyState
                icon={view === "saved" ? <Bookmark size={28} /> : <CheckCircle2 size={28} />}
                title={entryId ? "선택한 자료를 찾지 못했습니다" : emptyTitle}
                hint={
                  view === "saved"
                    ? "자료의 보관 버튼을 누르면 여기에 계속 남습니다."
                    : "검색어·출처·보기 방식을 바꾸거나 잠시 후 다시 확인해 주세요."
                }
              />
            </div>
          ) : (
            <div className="divide-y divide-edge overflow-hidden rounded-2xl border border-edge bg-surface">
              {data.items.map((item) => (
                <ResearchCard
                  key={item.entry_id}
                  item={item}
                  selected={item.entry_id === entryId}
                  onError={(message) => setNotice({ kind: "error", message })}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
