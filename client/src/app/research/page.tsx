"use client";

import {
  BookOpen,
  Check,
  CheckCircle2,
  Clock3,
  ExternalLink,
  RadioTower,
  RefreshCw,
} from "lucide-react";
import { useEffect, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  ResearchEntry,
  useFetchResearchQuery,
  useUpdateResearchReadStateMutation,
} from "@/state/api";

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

const replaceFiltersInUrl = (sourceId: string, unreadOnly: boolean) => {
  const url = new URL(window.location.href);
  if (sourceId) url.searchParams.set("source", sourceId);
  else url.searchParams.delete("source");
  if (unreadOnly) url.searchParams.set("filter", "unread");
  else url.searchParams.delete("filter");
  url.searchParams.delete("entry");
  window.history.replaceState(window.history.state, "", url);
};

function ResearchCard({ item, selected }: { item: ResearchEntry; selected: boolean }) {
  const [updateReadState, { isLoading }] = useUpdateResearchReadStateMutation();
  const authors = item.authors.filter(Boolean).join(", ");

  const markRead = () => {
    if (!item.is_read) void updateReadState({ entryId: item.entry_id, read: true });
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
              onClick={markRead}
            >
              원문 열기 <ExternalLink size={15} aria-hidden />
            </a>
            <button
              type="button"
              className="btn-secondary inline-flex items-center gap-1.5"
              onClick={() =>
                updateReadState({ entryId: item.entry_id, read: !item.is_read })
              }
              disabled={isLoading}
            >
              {item.is_read ? <BookOpen size={15} /> : <Check size={15} />}
              {item.is_read ? "읽지 않음으로" : "읽음 표시"}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

export default function ResearchPage() {
  const [sourceId, setSourceId] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [entryId, setEntryId] = useState("");
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setSourceId(params.get("source") ?? "");
    setUnreadOnly(params.get("filter") === "unread");
    setEntryId(params.get("entry") ?? "");
    setInitialized(true);
  }, []);

  const { data, isLoading, error, refetch, isFetching } = useFetchResearchQuery(
    {
      sourceId: sourceId || undefined,
      unreadOnly,
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

  const selectSource = (value: string) => {
    setSourceId(value);
    setEntryId("");
    replaceFiltersInUrl(value, unreadOnly);
  };

  const selectUnread = (value: boolean) => {
    setUnreadOnly(value);
    setEntryId("");
    replaceFiltersInUrl(sourceId, value);
  };

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        title="Research Radar"
        description="검증된 공개 출처에서 새로 발견한 퀀트 논문과 자료를 한곳에서 확인합니다"
        actions={
          <button
            type="button"
            className="btn-secondary inline-flex items-center gap-1.5"
            onClick={() => refetch()}
            disabled={!initialized || isFetching}
          >
            <RefreshCw size={15} className={isFetching ? "animate-spin" : ""} />
            새로고침
          </button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div className="rounded-2xl border border-edge bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <RadioTower size={15} /> 현재 목록
          </div>
          <p className="mt-2 text-2xl font-semibold text-ink num">{data?.total ?? 0}</p>
        </div>
        <div className="rounded-2xl border border-edge bg-surface p-4">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <BookOpen size={15} /> 읽지 않음
          </div>
          <p className="mt-2 text-2xl font-semibold text-ink num">{data?.unread ?? 0}</p>
        </div>
        <div className="col-span-2 rounded-2xl border border-edge bg-surface p-4 lg:col-span-1">
          <div className="flex items-center gap-2 text-xs text-ink-muted">
            <Clock3 size={15} /> 마지막 신규 반영
          </div>
          <p className="mt-2 text-sm font-medium text-ink">
            {data?.generated_at ? formatDateTime(data.generated_at) : "준비 중"}
          </p>
        </div>
      </div>

      {entryId && (
        <div className="rounded-xl border border-primary-500/30 bg-primary-500/10 px-4 py-3 text-sm text-primary-300">
          알림에서 선택한 자료를 표시하고 있습니다.
        </div>
      )}

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
        <button
          type="button"
          aria-pressed={unreadOnly}
          className={unreadOnly ? "btn-primary" : "btn-secondary"}
          onClick={() => selectUnread(!unreadOnly)}
        >
          읽지 않은 자료만
        </button>
      </section>

      {error ? (
        <div className="card">
          <ErrorState message="Research 피드를 불러오지 못했습니다." onRetry={refetch} />
        </div>
      ) : isLoading || !initialized ? (
        <div className="card">
          <LoadingState label="Research 피드를 불러오는 중..." />
        </div>
      ) : !data?.items.length ? (
        <div className="card">
          <EmptyState
            icon={<CheckCircle2 size={28} />}
            title={entryId ? "선택한 자료를 찾지 못했습니다" : "조건에 맞는 자료가 없습니다"}
            hint="출처 또는 읽음 필터를 바꾸거나 잠시 후 다시 확인해 주세요."
          />
        </div>
      ) : (
        <div className="space-y-3">
          {data.items.map((item) => (
            <ResearchCard key={item.entry_id} item={item} selected={item.entry_id === entryId} />
          ))}
        </div>
      )}
    </div>
  );
}
