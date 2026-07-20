import React from "react";

interface LoadingStateProps {
  label?: string;
  className?: string;
}

/** Inline, card-friendly loading indicator (not a fullscreen overlay). */
const LoadingState: React.FC<LoadingStateProps> = ({
  label = "Loading...",
  className = "",
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center py-16 gap-3 ${className}`.trim()}
    >
      <div
        className="w-8 h-8 rounded-full animate-spin"
        style={{
          border: "3px solid var(--border)",
          borderTopColor: "var(--primary)",
        }}
      />
      <p className="text-sm text-ink-muted">{label}</p>
    </div>
  );
};

export default LoadingState;
