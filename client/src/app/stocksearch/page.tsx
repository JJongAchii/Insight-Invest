"use client"

import { useState } from "react";
import MetaTable from "./MetaTable";

const StockSearch = () => {

  const [selectedData, setSelectedData] = useState([])

  return (
    <div className="grid grid-cols-1 xl:overflow-auto gap-10 pb-4 custom-grid-rows">
      <MetaTable onSelectionChange={setSelectedData}/>
      <div className="row-span-3 xl:row-span-6 bg-gray-500" />
      <div className="row-span-2 xl:row-span-3 col-span-1 md:col-span-2 xl:col-span-1 bg-gray-500"/>
    </div>
  );
}

export default StockSearch
