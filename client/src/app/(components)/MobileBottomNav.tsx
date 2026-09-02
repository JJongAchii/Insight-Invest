"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BellRing, BriefcaseBusiness, Home, LibraryBig, Search } from "lucide-react";
import ResearchUnseenBadge from "./ResearchUnseenBadge";

const items = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/actions", label: "Actions", icon: BellRing },
  { href: "/research", label: "Research", icon: LibraryBig },
  { href: "/stocksearch", label: "Search", icon: Search },
  { href: "/portfolio", label: "Portfolio", icon: BriefcaseBusiness },
];

export default function MobileBottomNav({
  researchUnseenCount,
}: {
  researchUnseenCount: number;
}) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Primary navigation"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t border-edge bg-surface/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
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
            <span className="relative">
              <Icon size={19} aria-hidden />
              {href === "/research" && (
                <ResearchUnseenBadge
                  count={researchUnseenCount}
                  className="absolute -right-4 -top-2"
                />
              )}
            </span>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
