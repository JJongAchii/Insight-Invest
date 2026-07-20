import React from "react";
import { Search } from "lucide-react";

export type SortKey = "name" | "return" | "sharpe";

interface SearchbarProps {
  search: string;
  onSearchChange: (value: string) => void;
  sortKey: SortKey;
  onSortChange: (key: SortKey) => void;
}

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "return", label: "Return" },
  { key: "sharpe", label: "Sharpe" },
];

const Searchbar: React.FC<SearchbarProps> = ({
  search,
  onSearchChange,
  sortKey,
  onSortChange,
}) => {
  return (
    <div className="flex flex-wrap gap-3">
      <div className="relative flex-grow min-w-[200px]">
        <input
          type="search"
          placeholder="Search strategies..."
          className="input pl-10"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="text-ink-muted" size={16} />
        </div>
      </div>
      <div className="flex gap-2">
        {SORT_OPTIONS.map((option) => (
          <button
            key={option.key}
            onClick={() => onSortChange(option.key)}
            className={
              sortKey === option.key
                ? "btn-secondary text-sm"
                : "btn-ghost text-sm"
            }
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Searchbar;
