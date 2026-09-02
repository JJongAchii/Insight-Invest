const displayCount = (count: number) => (count > 99 ? "99+" : String(count));

export default function ResearchUnseenBadge({
  count,
  className = "",
  collapsedOnDesktop = false,
}: {
  count: number;
  className?: string;
  collapsedOnDesktop?: boolean;
}) {
  if (count <= 0) return null;

  return (
    <span
      aria-label={`확인하지 않은 신규 리서치 ${count}개`}
      title={`확인하지 않은 신규 리서치 ${count}개`}
      className={`inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold leading-none text-white shadow-sm shadow-red-500/40 ${
        collapsedOnDesktop
          ? "md:absolute md:right-1.5 md:top-1.5 md:h-2.5 md:min-w-2.5 md:w-2.5 md:p-0 md:text-transparent md:ring-2 md:ring-surface"
          : ""
      } ${className}`}
    >
      <span aria-hidden>{displayCount(count)}</span>
    </span>
  );
}
