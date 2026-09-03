"use client";

import { useAppSelector } from "@/app/redux";
import {
  BellRing,
  BookOpenText,
  BriefcaseBusiness,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronDown,
  FlaskConical,
  Gauge,
  NotebookPen,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";

interface WorkspaceItem {
  href: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  activePrefixes?: string[];
  badge?: "actions" | "research";
}

const workspaces: WorkspaceItem[] = [
  { href: "/home", label: "브리핑", hint: "변화와 판단", icon: Gauge },
  {
    href: "/actions",
    label: "검토",
    hint: "지금 할 일",
    icon: BellRing,
    activePrefixes: ["/earnings"],
    badge: "actions",
  },
  {
    href: "/insight",
    label: "시장",
    hint: "흐름과 국면",
    icon: ChartNoAxesCombined,
    activePrefixes: ["/regime", "/stocksearch", "/stock/"],
  },
  {
    href: "/portfolio",
    label: "포트폴리오",
    hint: "노출과 기록",
    icon: BriefcaseBusiness,
    activePrefixes: ["/journal", "/optimization"],
  },
  {
    href: "/research",
    label: "리서치",
    hint: "근거와 전략",
    icon: BookOpenText,
    activePrefixes: ["/backtest"],
    badge: "research",
  },
];

const tools: Array<{
  href: string;
  label: string;
  icon: LucideIcon;
  activePrefixes?: string[];
}> = [
  { href: "/stocksearch", label: "종목 검색", icon: Search },
  { href: "/earnings", label: "실적 일정", icon: CalendarDays },
  { href: "/regime", label: "시장 국면", icon: ChartNoAxesCombined },
  { href: "/journal", label: "판단 기록", icon: NotebookPen },
  {
    href: "/backtest/strategy_list",
    label: "백테스트",
    icon: FlaskConical,
    activePrefixes: ["/backtest"],
  },
];

const isActiveRoute = (
  pathname: string,
  href: string,
  activePrefixes: string[] = []
) =>
  pathname === href ||
  pathname.startsWith(`${href}/`) ||
  activePrefixes.some((prefix) => pathname.startsWith(prefix)) ||
  (pathname === "/" && href === "/home");

const CountBadge = ({ count, label }: { count: number; label: string }) => {
  if (count <= 0) return null;
  const display = count > 99 ? "99+" : String(count);

  return (
    <span
      aria-label={`${label} ${count}개`}
      title={`${label} ${count}개`}
      className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-losses px-1.5 text-[10px] font-bold leading-none text-white shadow-sm shadow-rose-500/30 md:group-data-[collapsed=true]:absolute md:group-data-[collapsed=true]:right-1 md:group-data-[collapsed=true]:top-1 md:group-data-[collapsed=true]:h-2.5 md:group-data-[collapsed=true]:min-w-2.5 md:group-data-[collapsed=true]:w-2.5 md:group-data-[collapsed=true]:p-0 md:group-data-[collapsed=true]:text-transparent md:group-data-[collapsed=true]:ring-2 md:group-data-[collapsed=true]:ring-surface"
    >
      <span aria-hidden>{display}</span>
    </span>
  );
};

const Sidebar = ({
  isMobileOpen,
  onMobileClose,
  researchUnseenCount,
  actionCount,
}: {
  isMobileOpen: boolean;
  onMobileClose: () => void;
  researchUnseenCount: number;
  actionCount: number;
}) => {
  const isSidebarCollapsed = useAppSelector(
    (state) => state.global.isSidebarCollapsed
  );
  const pathname = usePathname();
  const utilityRouteActive = tools.some((item) =>
    isActiveRoute(pathname, item.href)
  );

  useEffect(() => {
    if (isMobileOpen) onMobileClose();
    // pathname 변경에만 반응해 모바일 탐색 후 본문을 즉시 보여준다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <aside
      data-collapsed={isSidebarCollapsed}
      className={`group fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col overflow-hidden border-r border-edge bg-surface/95 shadow-2xl shadow-black/30 backdrop-blur-xl transition-all duration-200 md:translate-x-0 md:shadow-none ${
        isMobileOpen ? "translate-x-0" : "-translate-x-full"
      } ${isSidebarCollapsed ? "md:w-[72px]" : "md:w-56"}`}
      aria-label="주요 탐색"
    >
      <div
        className={`flex min-h-[76px] items-center border-b border-edge px-5 ${
          isSidebarCollapsed ? "md:justify-center md:px-0" : ""
        }`}
      >
        <Link
          href="/home"
          className="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
          aria-label="Insight Invest 브리핑"
        >
          <Image
            src="/icons/icon-192.png"
            alt=""
            width={32}
            height={32}
            className="h-8 w-8 shrink-0 rounded-xl shadow-lg shadow-primary-500/20"
          />
          <span className={`${isSidebarCollapsed ? "md:hidden" : ""} min-w-0`}>
            <strong className="block truncate text-[15px] font-semibold tracking-[0.01em] text-ink">
              Insight Invest
            </strong>
            <span className="mt-0.5 block font-mono text-[8px] uppercase tracking-[0.18em] text-ink-muted">
              Decision instrument
            </span>
          </span>
        </Link>
        <button
          type="button"
          className="ml-auto rounded-lg p-2 text-ink-muted transition-colors hover:bg-raised hover:text-ink md:hidden"
          onClick={onMobileClose}
          aria-label="메뉴 닫기"
        >
          <X size={19} />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="작업공간">
        <p
          className={`${isSidebarCollapsed ? "md:hidden" : ""} mb-3 px-3 font-mono text-[9px] uppercase tracking-[0.16em] text-ink-muted`}
        >
          Workspace
        </p>
        <div className="space-y-1.5">
          {workspaces.map((item) => {
            const active = isActiveRoute(
              pathname,
              item.href,
              item.activePrefixes
            );
            const count =
              item.badge === "actions"
                ? actionCount
                : item.badge === "research"
                  ? researchUnseenCount
                  : 0;
            const badgeLabel =
              item.badge === "actions" ? "검토할 항목" : "새 리서치";
            const Icon = item.icon;

            return (
              <Link
                key={item.href}
                href={item.href}
                title={isSidebarCollapsed ? item.label : undefined}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-[48px] items-center gap-3 rounded-xl border px-3 transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400 ${
                  isSidebarCollapsed ? "md:justify-center md:px-0" : ""
                } ${
                  active
                    ? "border-primary-400/25 bg-gradient-to-r from-primary-500/15 to-secondary-400/5 text-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.03),0_10px_28px_rgba(3,5,14,0.16)]"
                    : "border-transparent text-ink-secondary hover:border-primary-400/10 hover:bg-primary-500/[0.05] hover:text-ink"
                }`}
              >
                {active && (
                  <span className="absolute -left-px h-5 w-[3px] rounded-r bg-gradient-to-b from-secondary-400 to-primary-400 shadow-[0_0_10px_rgba(124,91,255,0.35)]" />
                )}
                <Icon
                  size={18}
                  strokeWidth={1.75}
                  className={active ? "text-[color:var(--primary)]" : ""}
                  aria-hidden
                />
                <span className={`${isSidebarCollapsed ? "md:hidden" : ""} min-w-0`}>
                  <span className="block text-[13px] font-semibold">{item.label}</span>
                  <span className="mt-0.5 block text-[10px] text-ink-muted">
                    {item.hint}
                  </span>
                </span>
                <CountBadge count={count} label={badgeLabel} />
              </Link>
            );
          })}
        </div>

        <details
          className={`${isSidebarCollapsed ? "md:hidden" : ""} mt-6 border-t border-edge pt-3`}
          open={utilityRouteActive || undefined}
        >
          <summary className="flex cursor-pointer list-none items-center justify-between rounded-lg px-3 py-2 text-[11px] font-medium text-ink-secondary transition-colors hover:bg-raised hover:text-ink [&::-webkit-details-marker]:hidden">
            세부 도구
            <ChevronDown size={14} aria-hidden />
          </summary>
          <div className="mt-1 space-y-0.5">
            {tools.map(({ href, label, icon: Icon, activePrefixes }) => {
              const active = isActiveRoute(pathname, href, activePrefixes);
              return (
                <Link
                  key={href}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-xs transition-colors ${
                    active
                      ? "bg-raised text-[color:var(--primary)]"
                      : "text-ink-muted hover:bg-raised hover:text-ink-secondary"
                  }`}
                >
                  <Icon size={14} strokeWidth={1.7} aria-hidden />
                  {label}
                </Link>
              );
            })}
          </div>
        </details>
      </nav>

      <div className="border-t border-edge p-3">
        <Link
          href="/data-trust"
          title={isSidebarCollapsed ? "데이터 상태" : undefined}
          className={`flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs text-ink-muted transition-colors hover:bg-raised hover:text-ink-secondary ${
            isSidebarCollapsed ? "md:justify-center md:px-0" : ""
          }`}
        >
          <span className="relative">
            <ShieldCheck size={17} strokeWidth={1.7} aria-hidden />
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-primary-400 ring-2 ring-surface" />
          </span>
          <span className={isSidebarCollapsed ? "md:hidden" : ""}>데이터 상태 확인</span>
        </Link>
      </div>
    </aside>
  );
};

export default Sidebar;
