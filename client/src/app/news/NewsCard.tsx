"use client";

import React from "react";
import { NewsArticle } from "@/state/api";
import { IoOpenOutline, IoTimeOutline } from "react-icons/io5";

interface NewsCardProps {
  article: NewsArticle;
}

// Source brand colors
const SOURCE_COLORS: Record<string, { bg: string; text: string; accent: string }> = {
  reuters: { bg: "bg-orange-50", text: "text-orange-700", accent: "border-l-orange-500" },
  bbc: { bg: "bg-red-50", text: "text-red-700", accent: "border-l-red-500" },
  cnbc: { bg: "bg-blue-50", text: "text-blue-700", accent: "border-l-blue-500" },
  cnn: { bg: "bg-red-50", text: "text-red-700", accent: "border-l-red-500" },
  "ap news": { bg: "bg-slate-50", text: "text-slate-700", accent: "border-l-slate-500" },
  "the guardian": { bg: "bg-indigo-50", text: "text-indigo-700", accent: "border-l-indigo-500" },
  investing: { bg: "bg-emerald-50", text: "text-emerald-700", accent: "border-l-emerald-500" },
  "yahoo finance": { bg: "bg-purple-50", text: "text-purple-700", accent: "border-l-purple-500" },
  default: { bg: "bg-neutral-50", text: "text-neutral-700", accent: "border-l-primary-500" },
};

const NewsCard: React.FC<NewsCardProps> = ({ article }) => {
  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return "Recent";
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

    if (diffMins < 5) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffHours < 48) return "Yesterday";
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };

  const getSourceColors = (source: string) => {
    const key = source.toLowerCase();
    for (const [name, colors] of Object.entries(SOURCE_COLORS)) {
      if (key.includes(name)) return colors;
    }
    return SOURCE_COLORS.default;
  };

  const sourceColors = getSourceColors(article.source);

  return (
    <a
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`
        group block bg-white rounded-xl border-l-4 ${sourceColors.accent}
        shadow-sm hover:shadow-xl hover:shadow-neutral-200/50
        transition-all duration-300 cursor-pointer
        hover:-translate-y-1
      `}
    >
      <div className="p-5">
        {/* Header: Source & Time */}
        <div className="flex items-center justify-between mb-3">
          <span
            className={`
              text-xs font-bold uppercase tracking-wider px-2.5 py-1 rounded-md
              ${sourceColors.bg} ${sourceColors.text}
            `}
          >
            {article.source}
          </span>
          <div className="flex items-center gap-1.5 text-xs text-neutral-400 font-medium">
            <IoTimeOutline className="w-3.5 h-3.5" />
            {formatDate(article.published_at)}
          </div>
        </div>

        {/* Title - Large and Prominent */}
        <h3 className="text-base font-semibold text-neutral-800 leading-relaxed group-hover:text-primary-600 transition-colors line-clamp-3">
          {article.title}
        </h3>

        {/* Footer */}
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-neutral-100">
          <span className="text-xs text-neutral-400 font-medium">
            Read full article
          </span>
          <IoOpenOutline className="w-4 h-4 text-neutral-300 group-hover:text-primary-500 transition-colors" />
        </div>
      </div>
    </a>
  );
};

export default NewsCard;
