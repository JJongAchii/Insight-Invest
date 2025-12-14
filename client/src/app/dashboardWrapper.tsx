"use client";

import React, { useEffect } from "react";
import Navbar from "./(components)/Navbar";
import Sidebar from "./(components)/Sidebar";
import StoreProvider, { useAppSelector } from "./redux";

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    }
  }, [isDarkMode]);

  return (
    <div
      className={`${isDarkMode ? "dark" : "light"} flex bg-gradient-to-br from-primary-50 via-white to-secondary-50 text-neutral-900 w-full min-h-screen`}
    >
      <Sidebar />
      <main
        className={`
          flex flex-col w-full h-full py-6 px-6
          transition-all duration-200
          ${isSidebarCollapsed ? "md:pl-24" : "md:pl-[17rem]"}
        `}
      >
        <Navbar />
        <div className="flex-grow">{children}</div>
      </main>
    </div>
  );
};

const DashboardWrapper = ({ children }: { children: React.ReactNode }) => {
  return (
    <StoreProvider>
      <DashboardLayout>{children}</DashboardLayout>
    </StoreProvider>
  );
};

export default DashboardWrapper;
