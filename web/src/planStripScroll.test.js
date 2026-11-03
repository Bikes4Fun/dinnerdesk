import test from "node:test";
import assert from "node:assert/strict";
import { shouldScrollToNewMeal, planStripScrollPosition } from "./planStripScroll.js";

const plan = (id, count) => ({ id, slots: Array.from({ length: count }, (_, id) => ({ id })) });

test("first asynchronous load starts at the first meal", () => {
  assert.equal(shouldScrollToNewMeal(null, plan(1, 6)), false);
  assert.equal(shouldScrollToNewMeal(undefined, plan(1, 6)), false);
  assert.equal(shouldScrollToNewMeal(plan(1, 0), plan(1, 1)), false);
});

test("adding to the displayed week scrolls to the new meal", () => {
  assert.equal(shouldScrollToNewMeal(plan(1, 4), plan(1, 5)), true);
});

test("refresh, removal and a different week keep the initial position", () => {
  assert.equal(shouldScrollToNewMeal(plan(1, 4), plan(1, 4)), false);
  assert.equal(shouldScrollToNewMeal(plan(1, 4), plan(1, 3)), false);
  assert.equal(shouldScrollToNewMeal(plan(1, 4), plan(2, 6)), false);
  assert.equal(shouldScrollToNewMeal(plan(1, 4), null), false);
});


test("switching weeks explicitly resets an existing scrolled track", () => {
  assert.equal(planStripScrollPosition(plan(1, 4), plan(2, 4)), "start");
  assert.equal(planStripScrollPosition(plan(1, 4), plan(2, 6)), "start");
  assert.equal(planStripScrollPosition(null, plan(1, 4)), "start");
});

test("same-week refresh keeps position while an addition reveals the end", () => {
  assert.equal(planStripScrollPosition(plan(1, 4), plan(1, 4)), null);
  assert.equal(planStripScrollPosition(plan(1, 4), plan(1, 3)), null);
  assert.equal(planStripScrollPosition(plan(1, 4), plan(1, 5)), "end");
});
