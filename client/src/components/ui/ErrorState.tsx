import React from "react";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

/** Card-friendly error block with optional retry action. */
const ErrorState: React.FC<ErrorStateProps> = ({ message, onRetry }) => {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
        style={{
          backgroundColor: "color-mix(in srgb, var(--losses) 10%, transparent)",
        }}
      >
        <svg
          className="w-8 h-8 text-losses"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>
      <p className="text-losses text-lg font-medium mb-2">{message}</p>
      <p className="text-ink-muted text-sm mb-4">
        Please check your connection and try again
      </p>
      {onRetry && (
        <button onClick={onRetry} className="btn-primary">
          Try Again
        </button>
      )}
    </div>
  );
};

export default ErrorState;
