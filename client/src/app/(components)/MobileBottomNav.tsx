"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { dailyNavigation, marketNavigation, isActiveRoute } from "@/lib/navigation";

const items = [...dailyNavigation, ...marketNavigation].filter(item => item.mobileLabel);

export default function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="주요 탐색"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-primary-400/20 bg-surface/90 px-1 pb-[env(safe-area-inset-bottom)] shadow-[0_-16px_42px_rgba(3,5,14,0.26)] backdrop-blur-xl md:hidden"
    >
      {items.map(({ href, mobileLabel, icon: Icon, activePrefixes }) => {
        const active = isActiveRoute(pathname, href, activePrefixes);

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
            <Icon size={18} strokeWidth={active ? 2 : 1.7}
              className={active ? "text-[color:var(--primary)]" : ""} aria-hidden />
            {mobileLabel}
          </Link>
        );
      })}
    </nav>
  );
}
