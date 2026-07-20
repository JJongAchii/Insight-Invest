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
        <div className="flex items-center justify-between mb-4">
          {title && (
            <h3 className="text-base font-semibold text-ink">{title}</h3>
          )}
          {action && <div className="flex items-center gap-2">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
};

export default Card;
