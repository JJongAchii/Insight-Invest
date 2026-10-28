import type { LucideIcon } from "lucide-react";
import React from "react";

export function Pill({ className, children }: { className: string; children: React.ReactNode }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ${className}`}
    >
      {children}
    </span>
  );
}

export function Section({
  icon: Icon,
  title,
  meta,
  className = "",
  children,
}: {
  icon: LucideIcon;
  title: string;
  meta?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`card ${className}`.trim()} aria-label={title}>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
          <Icon size={17} className="text-primary-400" aria-hidden />
          {title}
        </h2>
        {meta && <div className="text-xs text-ink-muted">{meta}</div>}
      </div>
      {children}
    </section>
  );
}

export function EmptyLine({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed border-edge px-4 py-6 text-center text-sm text-ink-muted">
      {children}
    </p>
  );
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] text-ink-muted">{label}</dt>
      <dd className="mt-1 text-sm text-ink">{children}</dd>
    </div>
  );
}
