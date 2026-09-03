"use client";

import { useAppDispatch, useAppSelector } from "@/app/redux";
import { setIsDarkMode, setIsSidebarCollapsed } from "@/state";
import {
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  Search,
  ShieldCheck,
  Sun,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

const routeContexts = [
  { prefix: "/actions", title: "검토", detail: "지금 할 일" },
  { prefix: "/earnings", title: "검토", detail: "실적 일정" },
  { prefix: "/stocksearch", title: "시장", detail: "종목 검색" },
  { prefix: "/stock/", title: "시장", detail: "종목 상세" },
  { prefix: "/regime", title: "시장", detail: "시장 국면" },
  { prefix: "/insight", title: "시장", detail: "시장 흐름" },
  { prefix: "/journal", title: "포트폴리오", detail: "판단 기록" },
  { prefix: "/optimization", title: "포트폴리오", detail: "최적화" },
  { prefix: "/portfolio", title: "포트폴리오", detail: "노출과 위험" },
  { prefix: "/backtest/simulation", title: "리서치", detail: "전략 실험" },
  { prefix: "/backtest/strategy_list", title: "리서치", detail: "전략 보관함" },
  { prefix: "/research", title: "리서치", detail: "근거 피드" },
  { prefix: "/data-trust", title: "데이터 상태", detail: "출처와 최신성" },
] as const;

const Navbar = ({ onMobileMenuOpen }: { onMobileMenuOpen: () => void }) => {
  const dispatch = useAppDispatch();
  const router = useRouter();
  const pathname = usePathname();
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [todayLabel, setTodayLabel] = useState("오늘");
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const routeContext = routeContexts.find(({ prefix }) =>
    pathname.startsWith(prefix)
  );
  const isBriefing = pathname === "/" || pathname === "/home";

  useEffect(() => {
    setTodayLabel(
      new Intl.DateTimeFormat("ko-KR", {
        month: "long",
        day: "numeric",
        weekday: "long",
      }).format(new Date())
    );
  }, []);

  useEffect(() => {
    const focusSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const toggleSidebar = () => {
    if (window.matchMedia("(max-width: 767px)").matches) {
      onMobileMenuOpen();
      return;
    }
    dispatch(setIsSidebarCollapsed(!isSidebarCollapsed));
  };

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/stocksearch?q=${encodeURIComponent(value)}` : "/stocksearch");
  };

  const logout = async () => {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => null);
    window.location.replace("/login");
  };

  return (
    <header className="sticky top-3 z-30 mb-7 flex min-h-[60px] w-full items-center justify-between gap-3 rounded-2xl border border-edge bg-surface/75 px-3 shadow-[0_16px_44px_rgba(3,5,14,0.16)] backdrop-blur-xl md:top-5 md:px-4">
      <div className="flex min-w-0 items-center gap-2.5">
        <button
          type="button"
          className="rounded-xl p-2 text-ink-secondary transition-colors hover:bg-raised hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
          onClick={toggleSidebar}
          aria-label={isSidebarCollapsed ? "사이드바 펼치기" : "사이드바 접기 또는 메뉴 열기"}
        >
          <Menu className="md:hidden" size={20} aria-hidden />
          <PanelLeftClose className="hidden md:block" size={19} aria-hidden />
        </button>
        <div className="min-w-0 border-l border-edge pl-3">
          <strong className="block truncate text-sm font-semibold tracking-[-0.01em] text-ink sm:text-[15px]">
            {isBriefing ? todayLabel : routeContext?.title ?? "Insight Invest"}
          </strong>
          <span className="hidden text-[10px] text-ink-muted sm:block">
            {isBriefing ? "오늘의 판단 브리핑" : routeContext?.detail ?? "작업공간"}
          </span>
        </div>
      </div>

      <div className="flex min-w-0 items-center gap-1.5 sm:gap-2">
        <Link
          href="/data-trust"
          className="hidden items-center gap-2 border-r border-edge pr-4 text-[11px] text-ink-muted transition-colors hover:text-ink-secondary xl:flex"
        >
          <ShieldCheck size={14} strokeWidth={1.7} aria-hidden />
          데이터 상태
        </Link>

        <form onSubmit={handleSearch} role="search" className="relative hidden md:block">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
            size={15}
            aria-hidden
          />
          <input
            ref={searchRef}
            type="search"
            aria-label="종목 검색"
            placeholder="종목 검색"
            className="h-9 w-52 rounded-xl border border-edge bg-raised/60 pl-9 pr-12 text-xs text-ink outline-none transition-all placeholder:text-ink-muted focus:w-64 focus:border-primary-400/50 focus:ring-2 focus:ring-primary-400/15 lg:w-64 lg:focus:w-72"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-edge px-1.5 py-1 font-mono text-[8px] leading-none text-ink-muted">
            ⌘ K
          </kbd>
        </form>

        <button
          type="button"
          onClick={() => router.push("/stocksearch")}
          className="rounded-xl p-2 text-ink-secondary transition-colors hover:bg-raised hover:text-ink md:hidden"
          aria-label="종목 검색"
        >
          <Search size={19} aria-hidden />
        </button>
        <button
          type="button"
          onClick={() => dispatch(setIsDarkMode(!isDarkMode))}
          className="rounded-xl p-2 text-ink-secondary transition-colors hover:bg-raised hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
          aria-label={isDarkMode ? "라이트 모드로 전환" : "다크 모드로 전환"}
        >
          {isDarkMode ? (
            <Sun className="text-[color:var(--primary)]" size={19} aria-hidden />
          ) : (
            <Moon size={19} aria-hidden />
          )}
        </button>
        <button
          type="button"
          onClick={logout}
          className="rounded-xl p-2 text-ink-secondary transition-colors hover:bg-raised hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
          aria-label="로그아웃"
          title="로그아웃"
        >
          <LogOut size={18} aria-hidden />
        </button>
      </div>
    </header>
  );
};

export default Navbar;
