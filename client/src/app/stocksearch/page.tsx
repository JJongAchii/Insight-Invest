"use client";

import { useState } from "react";
import MetaTable from "./MetaTable";

const StockSearch = () => {
  // Selected rows state - will be used for future bulk actions
  const [, setSelectedData] = useState<unknown[]>([]);

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            Stock Search
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Search and explore stock metadata across US and Korean markets
          </p>
        </div>
      </div>

      {/* Meta Table */}
      <MetaTable onSelectionChange={setSelectedData} />
    </div>
  );
};

export default StockSearch;
