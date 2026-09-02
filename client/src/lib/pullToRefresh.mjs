export const PULL_DIRECTION_LOCK_PX = 8;
export const PULL_TRIGGER_DISTANCE_PX = 72;
export const PULL_MAX_VISUAL_DISTANCE_PX = 60;
export const PULL_VISUAL_RESISTANCE = 0.45;

/**
 * @param {{ overflowY: string, scrollHeight: number, clientHeight: number }} region
 */
export function isScrollableRegion({ overflowY, scrollHeight, clientHeight }) {
  return (
    (overflowY === "auto" || overflowY === "scroll") &&
    scrollHeight > clientHeight
  );
}

/**
 * @param {{ startX: number, startY: number, currentX: number, currentY: number }} points
 * @returns {{
 *   direction: "pending" | "cancelled" | "pulling",
 *   visualDistance: number,
 *   progress: number,
 *   armed: boolean,
 * }}
 */
export function measurePullMovement({ startX, startY, currentX, currentY }) {
  const deltaX = currentX - startX;
  const deltaY = currentY - startY;
  const largestDelta = Math.max(Math.abs(deltaX), Math.abs(deltaY));

  if (largestDelta < PULL_DIRECTION_LOCK_PX) {
    return { direction: "pending", visualDistance: 0, progress: 0, armed: false };
  }
  if (deltaY <= 0 || Math.abs(deltaX) >= deltaY) {
    return { direction: "cancelled", visualDistance: 0, progress: 0, armed: false };
  }

  return {
    direction: "pulling",
    visualDistance: Math.min(
      PULL_MAX_VISUAL_DISTANCE_PX,
      deltaY * PULL_VISUAL_RESISTANCE
    ),
    progress: Math.min(1, deltaY / PULL_TRIGGER_DISTANCE_PX),
    armed: deltaY >= PULL_TRIGGER_DISTANCE_PX,
  };
}
