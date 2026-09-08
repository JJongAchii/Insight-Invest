"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink } from "lucide-react";
import {
  useFetchNewsBriefingQuery,
  useFetchNewsQuery,
  NewsBriefingItem,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";

const formatDate = (value?: string | null) => {
  if (!value) return "기준시각 미확인";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat("ko-KR", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Seoul",
      }).format(date);
};

function BriefingRow({ item }: { item: NewsBriefingItem }) {
  return (
    <li>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group block rounded-lg py-3 hover:bg-raised/40"
      >
        <div className="flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
          <span>{item.source || "뉴스"}</span>
          {item.published_at && <time>{formatDate(item.published_at)}</time>}
          {item.cluster_count >= 3 && (
            <span>관련 기사 {item.cluster_count}건</span>
          )}
          <ExternalLink size={13} className="ml-auto" aria-hidden />
        </div>
        <h3 className="mt-1.5 text-[15px] font-semibold leading-6 text-ink group-hover:text-primary-300">
          {item.title}
        </h3>
        {item.why && (
          <p className="mt-1.5 text-[13px] leading-6 text-ink-secondary">
            {item.why}
          </p>
        )}
        {!!item.related_topics?.length && (
          <p className="mt-2 text-xs text-secondary-400">
            {item.related_topics.join(" · ")}
          </p>
        )}
      </a>
    </li>
  );
}

function LiveHeadlines({ category }: { category: "economy" | "topnews" }) {
  const {
    currentData: data,
    isFetching,
    error,
    refetch,
  } = useFetchNewsQuery({ category, region: "kr", limit: 5 });
  if (error)
    return (
      <ErrorState message="최신 뉴스를 불러오지 못했습니다" onRetry={refetch} />
    );
  if (!data && isFetching)
    return <LoadingState label="최신 헤드라인을 불러오는 중…" />;
  if (!data?.articles.length)
    return <EmptyState title="표시할 헤드라인이 없습니다" />;
  return (
    <div>
      <p className="mt-2 text-[11px] text-ink-muted">
        RSS 헤드라인 · 수집 {formatDate(data.fetched_at)}
      </p>
      <ul className="divide-y divide-edge">
        {data.articles.slice(0, 5).map((article) => (
          <BriefingRow
            key={article.id}
            item={{ ...article, cluster_count: 1, sources: [article.source] }}
          />
        ))}
      </ul>
    </div>
  );
}

export default function NewsBriefingCard() {
  const { data, isLoading, error, refetch } = useFetchNewsBriefingQuery(
    undefined,
    {
      pollingInterval: 10 * 60 * 1000,
      skipPollingIfUnfocused: true,
    },
  );
  const [tab, setTab] = useState<"economy" | "general">("economy");
  const [showLive, setShowLive] = useState(false);
  const sections = data?.active ? data.sections : undefined;
  const rows = sections?.[tab] ?? [];
  const liveOpen =
    showLive || (!isLoading && (rows.length === 0 || Boolean(error)));

  return (
    <Card headingLevel={2} title="경제 뉴스 브리핑">
      <div
        className="mb-3 flex flex-wrap items-center gap-2"
        aria-label="뉴스 분류"
      >
        {(["economy", "general"] as const).map((section) => (
          <button
            type="button"
            key={section}
            className="filter-chip"
            aria-pressed={tab === section}
            onClick={() => setTab(section)}
          >
            {section === "economy" ? "경제 · 시장" : "종합"}
          </button>
        ))}
      </div>
      {isLoading ? (
        <LoadingState label="뉴스 브리핑을 불러오는 중…" />
      ) : (
        <>
          {error && (
            <ErrorState
              message="선별 뉴스가 응답하지 않습니다. 최신 헤드라인을 함께 확인하세요."
              onRetry={refetch}
            />
          )}
          {sections && (
            <p className="text-[11px] text-ink-muted">
              {data?.edition === "morning"
                ? "아침판"
                : data?.edition === "evening"
                  ? "저녁판"
                  : "선별 뉴스"}{" "}
              · {formatDate(data?.as_of)} KST
            </p>
          )}
          {rows.length > 0 ? (
            <ul className="divide-y divide-edge">
              {rows.map((item) => (
                <BriefingRow key={item.url} item={item} />
              ))}
            </ul>
          ) : (
            !error && (
              <p className="py-2 text-xs leading-5 text-ink-muted">
                선별된 뉴스가 아직 없습니다. 최신{" "}
                {tab === "economy" ? "경제 " : ""}헤드라인을 확인하세요.
              </p>
            )
          )}
          {rows.length > 0 && (
            <button
              type="button"
              onClick={() => setShowLive((open) => !open)}
              aria-expanded={liveOpen}
              className="mt-2 flex min-h-10 items-center gap-1 text-xs text-primary-300"
            >
              <ChevronDown size={14} aria-hidden />
              최신 {tab === "economy" ? "경제 " : ""}헤드라인{" "}
              {liveOpen ? "접기" : "보기"}
            </button>
          )}
        </>
      )}
      {liveOpen && (
        <LiveHeadlines category={tab === "economy" ? "economy" : "topnews"} />
      )}
    </Card>
  );
}
