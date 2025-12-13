"use client"

import { useState } from "react";
import MetaTable from "./MetaTable";

const StockSearch = () => {

  const [selectedData, setSelectedData] = useState([])

  return (
    <div className="flex flex-col gap-8 pb-36">
      {/* Page Header */}
      <div className="mb-4">
        <h1 className="text-4xl font-bold mb-2">
          <span className="gradient-text">Stock Search</span>
        </h1>
        <p className="text-gray-600 text-lg">Search and explore stock metadata across US and Korean markets</p>
      </div>

      {/* Meta Table */}
      <MetaTable onSelectionChange={setSelectedData}/>
    </div>
  );
}

export default StockSearch
