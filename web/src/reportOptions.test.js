import test from "node:test";
import assert from "node:assert/strict";
import { ReportCatalog, PREP_REASONS, REPORT_REASONS, INGREDIENT_REPORT_REASONS } from "./reportOptions.js";

test("report ids preserve the API contract across screens", () => {
  assert.deepEqual(REPORT_REASONS.map(([id]) => id), ["ingredients", "steps", "diet", "photo", "duplicate", "turned_out", "other"]);
  assert.deepEqual(INGREDIENT_REPORT_REASONS.map(([id]) => id), ["name", "aisle", "amount", "photo", "duplicate", "other"]);
  assert.deepEqual(PREP_REASONS.map(([id]) => id), ["day_of", "kept_badly", "too_small", "prep_differently", "not_prep"]);
});

test("screens cannot mutate the shared vocabulary", () => {
  assert.throws(() => REPORT_REASONS.push(["oops", "Oops"]), TypeError);
  assert.throws(() => REPORT_REASONS[0][1] = "Changed", TypeError);
  const labels = ReportCatalog.labels("recipe");
  labels.photo = "Changed";
  assert.equal(ReportCatalog.labels("recipe").photo, "Photo doesn't match");
});

test("unknown report kinds fail instead of exposing object prototype properties", () => {
  assert.throws(() => ReportCatalog.choices("unknown"), /Unknown report kind/);
  assert.throws(() => ReportCatalog.choices("toString"), /Unknown report kind/);
});
