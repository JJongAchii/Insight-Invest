"use client";

import React, { useEffect, useState } from "react";
import Navbar from "./(components)/Navbar";
import Sidebar from "./(components)/Sidebar";
import MobileBottomNav from "./(components)/MobileBottomNav";
import PwaManager from "./(components)/PwaManager";
import PullToRefresh from "./(components)/PullToRefresh";
import StoreProvider, { useAppSelector } from "./redux";
import { usePathname } from "next/navigation";
import {
  useAcknowledgeResearchSeenMutation,
  useFetchActionsQuery,
  useFetchResearchStatusQuery,
} from "@/state/api";

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const { data: actionStatus } = useFetchActionsQuery(
    { horizonDays: 30 },
    {
      pollingInterval: 120_000,
      skipPollingIfUnfocused: true,
      refetchOnFocus: true,
      refetchOnReconnect: true,
    }
  );
  const { data: researchStatus } = useFetchResearchStatusQuery(undefined, {
    pollingInterval: 120_000,
    skipPollingIfUnfocused: true,
    refetchOnFocus: true,
    refetchOnReconnect: true,
  });
  const [acknowledgeResearchSeen] = useAcknowledgeResearchSeenMutation();

  useEffect(() => {
    if (researchStatus?.initialized !== false || !researchStatus.generated_at) return;
    void acknowledgeResearchSeen({ through: researchStatus.generated_at });
  }, [acknowledgeResearchSeen, researchStatus?.generated_at, researchStatus?.initialized]);

  const researchUnseenCount = researchStatus?.unseen ?? 0;
  const actionCount = actionStatus?.counts.badge ?? actionStatus?.counts.actionable ?? 0;

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
      className={`${isDarkMode ? "dark" : "light"} relative flex min-h-screen w-full overflow-x-clip bg-canvas text-ink`}
    >
      <Sidebar
        isMobileOpen={isMobileSidebarOpen}
        onMobileClose={() => setIsMobileSidebarOpen(false)}
        researchUnseenCount={researchUnseenCount}
        actionCount={actionCount}
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
          app-main-safe flex min-h-screen min-w-0 w-full flex-col px-4 pb-24 pt-3
          transition-[padding] duration-200 md:pb-6 md:pr-5 md:pt-5 lg:pr-8
          ${isSidebarCollapsed ? "md:pl-[5.75rem]" : "md:pl-[15.5rem]"}
        `}
      >
        <Navbar onMobileMenuOpen={() => setIsMobileSidebarOpen(true)} />
        <div className="mx-auto w-full max-w-[1560px] flex-grow">{children}</div>
      </main>
      <MobileBottomNav
        actionCount={actionCount}
        researchUnseenCount={researchUnseenCount}
      />
      {!isMobileSidebarOpen && <PullToRefresh />}
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
