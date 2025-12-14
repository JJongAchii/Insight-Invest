import React from "react";
import { Search } from "lucide-react";

const Searchbar = () => {
  return (
    <div className="flex flex-wrap gap-3">
      <div className="relative flex-grow min-w-[200px]">
        <input
          type="search"
          placeholder="Search strategies..."
          className="input pl-10"
        />
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search className="text-neutral-400" size={16} />
        </div>
      </div>
      <div className="flex gap-2">
        <button className="btn-ghost text-sm">Name</button>
        <button className="btn-ghost text-sm">Return</button>
        <button className="btn-ghost text-sm">Sharpe</button>
      </div>
    </div>
  );
};

export default Searchbar;
