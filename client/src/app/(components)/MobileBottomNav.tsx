"use client";

import {
  BellRing,
  BookOpenText,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  Gauge,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  activePrefixes: string[];
  badge?: "actions" | "research";
}

const items: NavItem[] = [
  { href: "/home", label: "브리핑", icon: Gauge, activePrefixes: [] },
  {
    href: "/actions",
    label: "검토",
    icon: BellRing,
    activePrefixes: ["/earnings"],
    badge: "actions",
  },
  {
    href: "/insight",
    label: "시장",
    icon: ChartNoAxesCombined,
    activePrefixes: ["/regime", "/stocksearch", "/stock/"],
  },
  {
    href: "/portfolio",
    label: "포트폴리오",
    icon: BriefcaseBusiness,
    activePrefixes: ["/journal", "/optimization"],
  },
  {
    href: "/research",
    label: "리서치",
    icon: BookOpenText,
    activePrefixes: ["/backtest"],
    badge: "research",
  },
];

const displayCount = (count: number) => (count > 99 ? "99+" : String(count));

export default function MobileBottomNav({
  actionCount,
  researchUnseenCount,
}: {
  actionCount: number;
  researchUnseenCount: number;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="주요 탐색"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-primary-400/20 bg-surface/90 px-1 pb-[env(safe-area-inset-bottom)] shadow-[0_-16px_42px_rgba(3,5,14,0.26)] backdrop-blur-xl md:hidden"
    >
      {items.map(({ href, label, icon: Icon, activePrefixes, badge }) => {
        const active =
          pathname === href ||
          pathname.startsWith(`${href}/`) ||
          activePrefixes.some((prefix) => pathname.startsWith(prefix)) ||
          (pathname === "/" && href === "/home");
        const count =
          badge === "actions"
            ? actionCount
            : badge === "research"
              ? researchUnseenCount
              : 0;

        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`relative flex min-h-[62px] flex-col items-center justify-center gap-1 text-[10px] font-medium transition-colors ${
              active ? "text-ink" : "text-ink-muted"
            }`}
          >
            {active && (
              <span className="absolute -top-px h-0.5 w-7 rounded-full bg-gradient-to-r from-primary-400 to-secondary-400 shadow-[0_0_12px_rgba(124,91,255,0.45)]" />
            )}
            <span className="relative">
              <Icon
                size={18}
                strokeWidth={active ? 2 : 1.7}
                className={active ? "text-[color:var(--primary)]" : ""}
                aria-hidden
              />
              {count > 0 && (
                <span
                  className="absolute -right-4 -top-2 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-losses px-1 font-mono text-[8px] font-bold leading-none text-white ring-2 ring-surface"
                  aria-label={`${label} ${count}개`}
                >
                  {displayCount(count)}
                </span>
              )}
            </span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
