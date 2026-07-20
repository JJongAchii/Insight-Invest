import React from "react";

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  hint?: string;
}

/** Card-friendly empty placeholder with optional icon and hint line. */
const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, hint }) => {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-raised flex items-center justify-center text-ink-muted">
        {icon ?? (
          <svg
            className="w-8 h-8"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        )}
      </div>
      <p className="text-ink-secondary font-medium">{title}</p>
      {hint && <p className="text-sm text-ink-muted mt-1">{hint}</p>}
    </div>
  );
};

export default EmptyState;
