import React from "react";
import { ArrowDownWideNarrow, Search } from "lucide-react";

export type SortKey = "name" | "return" | "sharpe";

interface SearchbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
}

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "name", label: "이름" },
  { key: "return", label: "수익률" },
  { key: "sharpe", label: "샤프" },
];

const Searchbar: React.FC<SearchbarProps> = ({
  search,
  onSearchChange,
  sortKey,
  onSortChange,
}) => {
  return (
    <div className="grid gap-5 border-b border-edge px-5 py-5 md:grid-cols-[minmax(260px,1fr)_auto] md:items-end md:px-6">
      <label className="block min-w-0">
        <span className="mb-2 block font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted">
          Registry query
        </span>
        <span className="relative block">
          <input
            type="search"
            placeholder="포트폴리오명 또는 전략명"
            className="input h-11 pl-10"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Search className="text-ink-muted" size={16} aria-hidden />
          </span>
        </span>
      </label>
      <div>
        <span className="mb-2 flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted">
          <ArrowDownWideNarrow size={12} aria-hidden />
          Sort evidence
        </span>
        <div className="segmented-control" aria-label="전략 정렬 기준">
          {SORT_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              onClick={() => onSortChange(option.key)}
              aria-pressed={sortKey === option.key}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Searchbar;
