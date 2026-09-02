import assert from "node:assert/strict";
import test from "node:test";

import {
  PULL_MAX_VISUAL_DISTANCE_PX,
  isScrollableRegion,
  measurePullMovement,
} from "../src/lib/pullToRefresh.mjs";

test("keeps small movement pending until direction is clear", () => {
  assert.equal(
    measurePullMovement({ startX: 10, startY: 10, currentX: 13, currentY: 16 })
      .direction,
    "pending"
  );
});

test("cancels upward and horizontal gestures", () => {
  assert.equal(
    measurePullMovement({ startX: 10, startY: 20, currentX: 10, currentY: 8 })
      .direction,
    "cancelled"
  );
  assert.equal(
    measurePullMovement({ startX: 10, startY: 10, currentX: 60, currentY: 35 })
      .direction,
    "cancelled"
  );
});

test("arms only after the downward trigger distance", () => {
  const shortPull = measurePullMovement({
    startX: 10,
    startY: 10,
    currentX: 12,
    currentY: 70,
  });
  const fullPull = measurePullMovement({
    startX: 10,
    startY: 10,
    currentX: 12,
    currentY: 82,
  });

  assert.equal(shortPull.direction, "pulling");
  assert.equal(shortPull.armed, false);
  assert.equal(fullPull.armed, true);
  assert.equal(fullPull.progress, 1);
});

test("caps the visual displacement on a long pull", () => {
  const movement = measurePullMovement({
    startX: 0,
    startY: 0,
    currentX: 0,
    currentY: 500,
  });

  assert.equal(movement.visualDistance, PULL_MAX_VISUAL_DISTANCE_PX);
});

test("recognizes nested scroll areas that must keep their own gesture", () => {
  assert.equal(
    isScrollableRegion({ overflowY: "auto", scrollHeight: 600, clientHeight: 300 }),
    true
  );
  assert.equal(
    isScrollableRegion({ overflowY: "hidden", scrollHeight: 600, clientHeight: 300 }),
    false
  );
  assert.equal(
    isScrollableRegion({ overflowY: "scroll", scrollHeight: 300, clientHeight: 300 }),
    false
  );
});
