import test from "node:test";
import assert from "node:assert/strict";
import { FilterOptions, PROTEINS, TIMES } from "./filterOptions.js";
import { cleanDiets, toggleDiet } from "./diet.js";

const ids = diets => FilterOptions.proteinsFor(diets).map(([id]) => id);

test("pescatarian choices include seafood and plant proteins without meat", () => {
  assert.deepEqual(ids(["pescatarian"]), ["salmon", "shrimp", "tofu", "white-fish", "tempeh", "beans", "eggs", "scallops"]);
});

test("vegetarian and vegan kitchens can express protein preferences", () => {
  assert.deepEqual(ids(["vegetarian"]), ["tofu", "tempeh", "beans", "eggs"]);
  assert.deepEqual(ids(["vegan"]), ["tofu", "tempeh", "beans"]);
});

test("strictest saved diet wins and additive diets do not block protein choices", () => {
  assert.deepEqual(ids(["omnivore", "vegan", "dairy-free"]), ids(["vegan"]));
  assert.deepEqual(FilterOptions.proteinsFor(["omnivore", "gluten-free"]), PROTEINS);
  assert.deepEqual(cleanDiets(["omnivore", "vegan", "gluten-free"]), ["vegan", "gluten-free"]);
  assert.deepEqual(toggleDiet(["vegan", "gluten-free"], "pescatarian"), ["pescatarian", "gluten-free"]);
});

test("every client offers the 20-minute option with the other cook times", () => {
  assert.deepEqual(TIMES.map(([id]) => id), ["any", "20", "30", "45"]);
});
