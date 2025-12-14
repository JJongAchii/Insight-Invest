"use client";

import React from "react";
import { NewsArticle } from "@/state/api";
import NewsCard from "./NewsCard";

interface NewsGridProps {
  articles: NewsArticle[];
  isLoading: boolean;
}

const NewsGrid: React.FC<NewsGridProps> = ({ articles, isLoading }) => {
  if (articles.length === 0) {
    return (
      <div className="card text-center py-16">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-neutral-100 flex items-center justify-center">
          <svg
            className="w-8 h-8 text-neutral-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"
            />
          </svg>
        </div>
        <p className="text-neutral-600 font-medium">No news articles found</p>
        <p className="text-sm text-neutral-400 mt-1">
          Try adjusting your filters or check back later
        </p>
      </div>
    );
  }

  return (
    <div
      className={`
      grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5
      ${isLoading ? "opacity-50 pointer-events-none" : ""}
      transition-opacity duration-300
    `}
    >
      {articles.map((article) => (
        <NewsCard key={article.id} article={article} />
      ))}
    </div>
  );
};

export default NewsGrid;
