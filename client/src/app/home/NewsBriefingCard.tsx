"use client";

import React, { useState } from "react";
import { IoChevronDown, IoOpenOutline, IoNewspaperOutline } from "react-icons/io5";

import {
  useFetchNewsBriefingQuery,
  useFetchNewsQuery,
  NewsBriefingItem,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";

// 언론사 칩 색 (theme-aware tint — NewsCompactList 관례 계승, 국내 언론사판)
const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  연합뉴스: { bg: "bg-blue-500/10", text: "text-blue-400" },
  한국경제: { bg: "bg-sky-500/10", text: "text-sky-400" },
  매일경제: { bg: "bg-amber-500/10", text: "text-amber-400" },
  조선일보: { bg: "bg-slate-500/10", text: "text-slate-400" },
  중앙일보: { bg: "bg-indigo-500/10", text: "text-indigo-400" },
  동아일보: { bg: "bg-teal-500/10", text: "text-teal-400" },
  한겨레: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
  경향신문: { bg: "bg-lime-500/10", text: "text-lime-400" },
  KBS: { bg: "bg-red-500/10", text: "text-red-400" },
  MBC: { bg: "bg-rose-500/10", text: "text-rose-400" },
  SBS: { bg: "bg-orange-500/10", text: "text-orange-400" },
  YTN: { bg: "bg-cyan-500/10", text: "text-cyan-400" },
  머니투데이: { bg: "bg-violet-500/10", text: "text-violet-400" },
  서울경제: { bg: "bg-fuchsia-500/10", text: "text-fuchsia-400" },
  default: { bg: "bg-raised", text: "text-ink-secondary" },
};

const getSourceColors = (source: string) => {
  for (const [name, colors] of Object.entries(SOURCE_COLORS)) {
    if (name !== "default" && source.includes(name)) return colors;
  }
  return SOURCE_COLORS.default;
};

const EDITION_LABEL: Record<string, string> = {
  morning: "아침판",
  evening: "저녁판",
};

const formatAsOf = (iso?: string): string => {
  if (!iso) return "";
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}/${dd} ${hh}:${mi}`;
};

const BriefingRow: React.FC<{ item: NewsBriefingItem }> = ({ item }) => {
  const colors = getSourceColors(item.source);
  return (
    <li>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex flex-col gap-1 py-3 px-1 rounded-lg hover:bg-raised transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md ${colors.bg} ${colors.text}`}
          >
            {item.source || "뉴스"}
          </span>
          <span className="flex-1 min-w-0 text-sm text-ink truncate group-hover:text-primary-400 transition-colors">
            {item.title}
          </span>
          {item.cluster_count >= 3 && (
            <span className="shrink-0 flex items-center gap-1 text-[10px] text-ink-muted">
              <IoNewspaperOutline className="w-3 h-3" aria-hidden />
              {item.cluster_count}개 언론사
            </span>
          )}
          <IoOpenOutline
            className="shrink-0 w-4 h-4 text-ink-muted group-hover:text-primary-400 transition-colors"
            aria-hidden
          />
        </div>
        {item.why && (
          <p className="text-xs text-ink-muted pl-1 line-clamp-2">{item.why}</p>
        )}
      </a>
    </li>
  );
};

/** 라이브 최신 헤드라인 (기존 /news 라우트, KR) — 접었을 땐 fetch 안 함 */
const LiveHeadlines: React.FC<{ open: boolean }> = ({ open }) => {
  const { data, isLoading, error, refetch } = useFetchNewsQuery(
    { category: "topnews", region: "kr", limit: 5 },
    { skip: !open },
  );
  if (!open) return null;
  if (error) return <ErrorState message="Failed to load news" onRetry={refetch} />;
  if (isLoading || !data) return <LoadingState label="헤드라인을 불러오는 중..." />;
  const articles = data.articles.slice(0, 5);
  if (articles.length === 0) return <EmptyState title="헤드라인 없음" />;
  return (
    <ul className="flex flex-col divide-y divide-edge">
      {articles.map((a) => {
        const colors = getSourceColors(a.source);
        return (
          <li key={a.id}>
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 py-2 px-1 rounded-lg hover:bg-raised transition-colors"
            >
              <span
                className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md ${colors.bg} ${colors.text}`}
              >
                {a.source}
              </span>
              <span className="flex-1 min-w-0 text-sm text-ink truncate group-hover:text-primary-400 transition-colors">
                {a.title}
              </span>
            </a>
          </li>
        );
      })}
    </ul>
  );
};

/** 홈 카드: 큐레이션된 오늘의 중요 뉴스 + 접이식 라이브 헤드라인. */
const NewsBriefingCard: React.FC = () => {
  // 주중 08~19시 매시 폴러가 발행을 갱신하므로, 열려 있는 홈도 10분마다 따라간다
  const { data, isLoading } = useFetchNewsBriefingQuery(undefined, {
    pollingInterval: 10 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });
  const [tab, setTab] = useState<"general" | "economy">("general");
  const [showLive, setShowLive] = useState(false);

  const sections = data?.active ? data.sections : undefined;
  const active = Boolean(sections);
  const rows = sections ? sections[tab] : [];
  const liveOpen = showLive || !active;

  return (
    <Card title="오늘의 중요 뉴스">
      {isLoading ? (
        <LoadingState label="뉴스를 불러오는 중..." />
      ) : (
        <div className="flex flex-col gap-2">
          {active ? (
            <>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-ink-muted">
                  {EDITION_LABEL[data?.edition ?? ""] ?? ""} {formatAsOf(data?.as_of)}
                </span>
                <div className="ml-auto flex gap-1">
                  {(["general", "economy"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setTab(s)}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                        tab === s
                          ? "bg-primary-500/15 text-primary-400 font-semibold"
                          : "text-ink-muted hover:bg-raised"
                      }`}
                    >
                      {s === "general" ? "종합" : "경제"}
                    </button>
                  ))}
                </div>
              </div>
              {rows.length === 0 ? (
                <EmptyState title="선정된 뉴스 없음" />
              ) : (
                <ul className="flex flex-col divide-y divide-edge">
                  {rows.map((item) => (
                    <BriefingRow key={item.url} item={item} />
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-xs text-ink-muted px-1">
              아직 오늘의 브리핑이 없습니다 — 최신 헤드라인을 확인하세요.
            </p>
          )}
          {active && (
            <button
              onClick={() => setShowLive((v) => !v)}
              aria-expanded={liveOpen}
              className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink transition-colors pt-1"
            >
              <IoChevronDown
                className={`w-3.5 h-3.5 transition-transform ${liveOpen ? "rotate-180" : ""}`}
                aria-hidden
              />
              최신 헤드라인
            </button>
          )}
          <LiveHeadlines open={liveOpen} />
        </div>
      )}
    </Card>
  );
};

export default NewsBriefingCard;
