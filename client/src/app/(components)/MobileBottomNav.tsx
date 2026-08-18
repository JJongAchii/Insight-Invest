"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BriefcaseBusiness, Home, Search } from "lucide-react";

const items = [
  { href: "/home", label: "홈", icon: Home },
  { href: "/insight", label: "시장", icon: BarChart3 },
  { href: "/stocksearch", label: "종목", icon: Search },
  { href: "/portfolio", label: "자산", icon: BriefcaseBusiness },
];

export default function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="주요 메뉴"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-edge bg-surface/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      {items.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`flex min-h-14 flex-col items-center justify-center gap-1 text-xs font-medium ${
              active ? "text-primary-400" : "text-ink-muted"
            }`}
          >
            <Icon size={19} aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
