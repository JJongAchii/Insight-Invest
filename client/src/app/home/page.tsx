"use client"

const Home = () => {
  return (
    <div className="grid grid-cols-1 xl:overflow-auto gap-10 pb-4 custom-grid-rows">
      <div className="row-span-3 xl:row-span-6 bg-gray-500"/>
      <div className="row-span-3 xl:row-span-6 bg-gray-500"/>
      <div className="row-span-2 xl:row-span-3 col-span-1 md:col-span-2 xl:col-span-1 bg-gray-500"/>
    </div>
  );
}

export default Home