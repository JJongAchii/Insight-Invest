import React from "react";

interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
  meta?: React.ReactNode;
}

/** Workspace heading: a quiet title block tied to the app's decision-signal spine. */
const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  description,
  actions,
  eyebrow,
  meta,
}) => {
  return (
    <header className="relative flex flex-col gap-5 py-1 sm:flex-row sm:items-end sm:justify-between">
      <span
        aria-hidden
        className="absolute bottom-1 left-0 top-1 w-px bg-gradient-to-b from-primary-400 via-primary-500 to-secondary-400"
      />
      <span
        aria-hidden
        className="absolute left-[-3px] top-2 h-[7px] w-[7px] rounded-full border border-primary-300 bg-canvas shadow-[0_0_12px_rgba(155,126,255,0.65)]"
      />
      <div className="min-w-0 pl-5">
        {eyebrow && (
          <p className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-primary-300">
            {eyebrow}
          </p>
        )}
        <h1 className="page-title">{title}</h1>
        {description && <p className="page-description max-w-3xl">{description}</p>}
        {meta && (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
            {meta}
          </div>
        )}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2 pl-5 sm:justify-end sm:pl-0">
          {actions}
        </div>
      )}
    </header>
  );
};

export default PageHeader;
