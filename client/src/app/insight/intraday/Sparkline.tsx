import React from "react";

/** 축 없는 미니 라인 — 지수 타일용. 값 범위를 뷰박스에 정규화만 한다. */
const Sparkline = ({
  points,
  color,
  width = 96,
  height = 28,
}: {
  points: number[];
  color: string;
  width?: number;
  height?: number;
}) => {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(
      height - ((v - min) / span) * (height - 4) - 2
    ).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
};

export default Sparkline;
