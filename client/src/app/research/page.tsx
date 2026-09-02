"use client";

import {
  Bookmark,
  BookOpen,
  Check,
  CheckCheck,
  CheckCircle2,
  Clock3,
  ExternalLink,
  LibraryBig,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  ResearchEntry,
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

const parseView = (value: string | null): ResearchView => {
  if (VIEW_OPTIONS.some((option) => option.value === value)) return value as ResearchView;
  return "all";
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

const replaceLibraryUrl = (sourceId: string, view: ResearchView, query: string) => {
  const url = new URL(window.location.href);
  if (sourceId) url.searchParams.set("source", sourceId);
  else url.searchParams.delete("source");
  if (view !== "all") url.searchParams.set("view", view);
  else url.searchParams.delete("view");
  if (query) url.searchParams.set("q", query);
  else url.searchParams.delete("q");
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
      className={`rounded-2xl border bg-surface p-4 transition-colors sm:p-5 ${
        selected ? "border-primary-400 ring-2 ring-primary-500/20" : "border-edge"
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
            {!item.is_read && (
              <span className="rounded-full bg-primary-500/15 px-2 py-0.5 font-medium text-primary-400">
                New
              </span>
            )}
            {item.is_saved && (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary-500/15 px-2 py-0.5 font-medium text-primary-300">
                <Bookmark size={11} fill="currentColor" aria-hidden /> 보관됨
              </span>
            )}
            <span className="inline-flex items-center gap-1 sm:ml-auto">
              <Clock3 size={13} aria-hidden />
              {formatDate(item.published_at || item.discovered_at)}
            </span>
          </div>

          <h2 className="mt-2 text-base font-semibold leading-6 text-ink sm:text-lg">
            {item.title}
          </h2>
          {authors && <p className="mt-1 text-xs text-ink-muted">{authors}</p>}
          <p className="mt-3 text-sm leading-6 text-ink-secondary">
            {item.summary || "공개 출처에 별도 요약이 없습니다. 원문에서 내용을 확인해 주세요."}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary inline-flex items-center gap-1.5"
              onClick={markReadOnOpen}
            >
              원문 열기 <ExternalLink size={15} aria-hidden />
            </a>
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1.5"
              onClick={() => void toggleRead()}
              disabled={isUpdatingRead}
            >
              {item.is_read ? <BookOpen size={15} /> : <Check size={15} />}
              {item.is_read ? "안 읽음으로" : "읽음 표시"}
            </button>
            <button
              type="button"
              aria-pressed={item.is_saved}
              className={`btn-secondary inline-flex items-center gap-1.5 ${
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
    replaceLibraryUrl(value, view, query);
  };

  const selectView = (value: ResearchView) => {
    setView(value);
    setEntryId("");
    replaceLibraryUrl(sourceId, value, query);
  };

  const clearSearch = () => {
    setSearchInput("");
    setQuery("");
    setEntryId("");
    replaceLibraryUrl(sourceId, view, "");
  };

  const markEverythingRead = async () => {
    const unread = data?.unread ?? 0;
    if (!unread) return;
    if (!window.confirm(`읽지 않은 자료 ${unread}건을 모두 읽음으로 표시할까요?`)) return;
    try {
      const result = await markAllRead().unwrap();
      setView("all");
      setEntryId("");
      replaceLibraryUrl(sourceId, "all", query);
      setNotice({
        kind: "success",
        message: `${result.updated}건을 읽음으로 표시했습니다. 자료는 전체와 읽음에서 계속 볼 수 있습니다.`,
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
        title="Research Library"
        description="새 자료를 발견하고, 읽고, 다시 찾을 자료를 보관하는 개인 퀀트 리서치 서재"
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

      <section className="space-y-3 rounded-2xl border border-edge bg-surface p-4 sm:p-5">
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
            className="input w-full pl-10 pr-10"
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

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="리서치 보기 방식">
          {VIEW_OPTIONS.map((option) => {
            const Icon = option.icon;
            const active = view === option.value;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={active}
                onClick={() => selectView(option.value)}
                className={`flex items-center justify-between gap-2 rounded-xl border px-3 py-3 text-sm transition-colors ${
                  active
                    ? "border-primary-500 bg-primary-500/15 text-primary-300"
                    : "border-edge bg-surface-raised text-ink-secondary hover:text-ink"
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  <Icon size={16} /> {option.label}
                </span>
                <span className="num text-xs">{counts[option.value]}</span>
              </button>
            );
          })}
        </div>

        <p className="text-xs leading-5 text-ink-muted">
          읽음은 삭제가 아닙니다. 전체 또는 읽음에서 언제든 다시 보고, 중요한 자료는 보관함에
          따로 남길 수 있습니다.
        </p>
      </section>

      <section className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-4 sm:flex-row sm:items-end">
        <label className="flex min-w-0 flex-1 flex-col gap-1.5 text-xs font-medium text-ink-muted">
          출처
          <select
            value={sourceId}
            onChange={(event) => selectSource(event.target.value)}
            className="input w-full"
          >
            <option value="">모든 출처</option>
            {data?.sources.map((source) => (
              <option key={source.source_id} value={source.source_id}>
                {source.source_name} ({source.count})
              </option>
            ))}
          </select>
        </label>
        <div className="flex min-w-44 flex-col gap-1 text-xs text-ink-muted sm:text-right">
          <span>
            결과 <strong className="font-semibold text-ink">{data?.total ?? 0}</strong>건
          </span>
          <span>
            마지막 반영 {data?.generated_at ? formatDateTime(data.generated_at) : "준비 중"}
          </span>
        </div>
      </section>

      {error ? (
        <div className="card">
          <ErrorState message="Research Library를 불러오지 못했습니다." onRetry={refetch} />
        </div>
      ) : isLoading || !initialized ? (
        <div className="card">
          <LoadingState label="Research Library를 불러오는 중..." />
        </div>
      ) : !data?.items.length ? (
        <div className="card">
          <EmptyState
            icon={view === "saved" ? <Bookmark size={28} /> : <CheckCircle2 size={28} />}
            title={entryId ? "선택한 자료를 찾지 못했습니다" : emptyTitle}
            hint={
              view === "saved"
                ? "자료 카드의 보관 버튼을 누르면 여기에 계속 남습니다."
                : "검색어·출처·보기 방식을 바꾸거나 잠시 후 다시 확인해 주세요."
            }
          />
        </div>
      ) : (
        <div className="space-y-3">
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
    </div>
  );
}
