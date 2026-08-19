"use client";

import React, { useEffect, useState } from "react";
import Navbar from "./(components)/Navbar";
import Sidebar from "./(components)/Sidebar";
import MobileBottomNav from "./(components)/MobileBottomNav";
import PwaManager from "./(components)/PwaManager";
import StoreProvider, { useAppSelector } from "./redux";
import { usePathname } from "next/navigation";

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.remove("light");
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    }
  }, [isDarkMode]);

  useEffect(() => {
    if (!isMobileSidebarOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsMobileSidebarOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isMobileSidebarOpen]);

  return (
    <div
      className={`${isDarkMode ? "dark" : "light"} flex text-ink w-full min-h-screen`}
    >
      <Sidebar
        isMobileOpen={isMobileSidebarOpen}
        onMobileClose={() => setIsMobileSidebarOpen(false)}
      />
      {isMobileSidebarOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/55 backdrop-blur-[1px] md:hidden"
          onClick={() => setIsMobileSidebarOpen(false)}
          aria-label="메뉴 닫기"
        />
      )}
      <main
        className={`
          app-main-safe flex min-w-0 flex-col w-full h-full px-4 pb-24 pt-4 md:px-6 md:pb-6 md:pt-6
          transition-all duration-200
          ${isSidebarCollapsed ? "md:pl-24" : "md:pl-[17rem]"}
        `}
      >
        <Navbar onMobileMenuOpen={() => setIsMobileSidebarOpen(true)} />
        <div className="flex-grow">{children}</div>
      </main>
      <MobileBottomNav />
      <PwaManager />
    </div>
  );
};

const DashboardWrapper = ({ children }: { children: React.ReactNode }) => {
  const pathname = usePathname();
  if (pathname === "/login" || pathname === "/offline") return <>{children}</>;

  return (
    <StoreProvider>
      <DashboardLayout>{children}</DashboardLayout>
    </StoreProvider>
  );
};

export default DashboardWrapper;
