import {
  BellRing,
  BookOpenText,
  BriefcaseBusiness,
  CalendarDays,
  ChartNoAxesCombined,
  FlaskConical,
  Globe2,
  LayoutDashboard,
  NotebookPen,
  Search,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavigationItem {
  href: string;
  label: string;
  hint: string;
  icon: LucideIcon;
  activePrefixes?: string[];
  badge?: "actions" | "research";
}

export const marketNavigation: NavigationItem[] = [
  {
    href: "/home",
    label: "시장 브리핑",
    hint: "시황 · 경제 · 읽을거리",
    icon: LayoutDashboard,
  },
  {
    href: "/insight",
    label: "한국 시장",
    hint: "지수 · 수급 · 섹터",
    icon: ChartNoAxesCombined,
  },
  {
    href: "/regime",
    label: "경제 · 매크로",
    hint: "금리 · 물가 · 경기 국면",
    icon: Globe2,
  },
  {
    href: "/research",
    label: "리서치",
    hint: "논문 · 자료 · 근거 탐색",
    icon: BookOpenText,
    badge: "research",
  },
  {
    href: "/stocksearch",
    label: "종목 탐색",
    hint: "검색 · 비교 · 기업 분석",
    icon: Search,
    activePrefixes: ["/stock/"],
  },
  {
    href: "/earnings",
    label: "실적 일정",
    hint: "주요 기업 발표와 결과",
    icon: CalendarDays,
  },
];

export const personalNavigation: NavigationItem[] = [
  {
    href: "/portfolio",
    label: "포트폴리오",
    hint: "",
    icon: BriefcaseBusiness,
    activePrefixes: ["/optimization"],
  },
  {
    href: "/actions",
    label: "검토 알림",
    hint: "",
    icon: BellRing,
    badge: "actions",
  },
  { href: "/journal", label: "판단 기록", hint: "", icon: NotebookPen },
  {
    href: "/backtest/strategy_list",
    label: "백테스트",
    hint: "",
    icon: FlaskConical,
    activePrefixes: ["/backtest"],
  },
];

export const isActiveRoute = (
  pathname: string,
  href: string,
  activePrefixes: string[] = [],
) =>
  pathname === href ||
  pathname.startsWith(`${href}/`) ||
  activePrefixes.some((prefix) => pathname.startsWith(prefix)) ||
  (pathname === "/" && href === "/home");
