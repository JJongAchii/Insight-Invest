import React from "react";

interface CardProps {
  title?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

/** Token-aware surface card with an optional title/action header row. */
const Card: React.FC<CardProps> = ({ title, action, className = "", children }) => {
  return (
    <div className={`card ${className}`.trim()}>
      {(title || action) && (
        <div className="mb-4 flex min-w-0 flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
          {title && (
            <h3 className="min-w-0 text-base font-semibold text-ink">{title}</h3>
          )}
          {action && <div className="flex min-w-0 flex-wrap items-center gap-2">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
};

export default Card;
