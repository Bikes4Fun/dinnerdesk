import test from "node:test";
import assert from "node:assert/strict";
import { RecipeCollections } from "./recipeCollections.js";

test("reviewed filter uses admin approval, independently of photos and other tags", () => {
  const rows = [
    { id: 1, name: "Reviewed", reviewed: true, favorited: true },
    { id: 2, name: "Photo only", photo_tested: true, tags: ["reviewed"], favorited: true },
    { id: 3, name: "Unreviewed", reviewed: false },
    { id: 4, name: "Reviewed extra", reviewed: true, tags: ["sauce"] },
  ];
  const lists = new RecipeCollections(rows);
  assert.deepEqual(lists.filter(rows, ["reviewed"]).map((r) => r.id), [1, 4]);
  assert.deepEqual(lists.filter(rows, ["reviewed", "fav"]).map((r) => r.id), [1]);
  assert.equal(lists.filter(rows, []).length, rows.length);
  assert.ok(RecipeCollections.FILTERS.some(([id]) => id === "reviewed"));
});
