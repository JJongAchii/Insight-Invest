"use client";

import React from "react";
import { IoOpenOutline, IoTimeOutline } from "react-icons/io5";

import { useFetchNewsQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";

// Source brand colors (theme-aware: tinted backgrounds work on dark & light)
const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  reuters: { bg: "bg-orange-500/10", text: "text-orange-400" },
  bbc: { bg: "bg-red-500/10", text: "text-red-400" },
  cnbc: { bg: "bg-blue-500/10", text: "text-blue-400" },
  cnn: { bg: "bg-red-500/10", text: "text-red-400" },
  "ap news": { bg: "bg-slate-500/10", text: "text-slate-400" },
  "the guardian": { bg: "bg-indigo-500/10", text: "text-indigo-400" },
  investing: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
  "yahoo finance": { bg: "bg-purple-500/10", text: "text-purple-400" },
  default: { bg: "bg-raised", text: "text-ink-secondary" },
};

const getSourceColors = (source: string) => {
  const key = source.toLowerCase();
  for (const [name, colors] of Object.entries(SOURCE_COLORS)) {
    if (key.includes(name)) return colors;
  }
  return SOURCE_COLORS.default;
};

const formatRelative = (dateStr: string | null): string => {
  if (!dateStr) return "Recent";
  const date = new Date(dateStr);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffMins < 5) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffHours < 48) return "Yesterday";
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

/** Dashboard card: compact list of the latest top-news headlines. */
const NewsCompactList: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchNewsQuery({
    category: "topnews",
    limit: 5,
  });

  const articles = (data?.articles ?? []).slice(0, 5);

  return (
    <Card title="최신 뉴스">
      {error ? (
        <ErrorState message="Failed to load news" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="뉴스를 불러오는 중..." />
      ) : articles.length === 0 ? (
        <EmptyState title="No news" />
      ) : (
        <ul className="flex flex-col divide-y divide-edge">
          {articles.map((article) => {
            const colors = getSourceColors(article.source);
            return (
              <li key={article.id}>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex items-center gap-3 py-3 px-1 rounded-lg
                             hover:bg-raised transition-colors"
                >
                  <span
                    className={`shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md ${colors.bg} ${colors.text}`}
                  >
                    {article.source}
                  </span>
                  <span className="flex-1 min-w-0 text-sm text-ink truncate group-hover:text-primary-400 transition-colors">
                    {article.title}
                  </span>
                  <span className="shrink-0 flex items-center gap-1 text-xs text-ink-muted">
                    <IoTimeOutline className="w-3.5 h-3.5" aria-hidden />
                    {formatRelative(article.published_at)}
                  </span>
                  <IoOpenOutline
                    className="shrink-0 w-4 h-4 text-ink-muted group-hover:text-primary-400 transition-colors"
                    aria-hidden
                  />
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
};

export default NewsCompactList;
