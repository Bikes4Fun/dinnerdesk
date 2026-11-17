import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { PrepTaskPresentation, prepMealGroups } from "../src/PrepTaskPresentation.js";

const fixture = JSON.parse(readFileSync(new URL("../../tests/fixtures/prep_presentation.json", import.meta.url)));

test("prep cached fallback matches the shared platform contract and preserves source", () => {
  const task = structuredClone(fixture.task);
  assert.deepEqual(new PrepTaskPresentation(task).instructionGroups, fixture.expected);
  assert.deepEqual(task, fixture.task);
});

test("server instruction groups are authoritative, including an empty result", () => {
  assert.deepEqual(new PrepTaskPresentation({ ...fixture.task, instruction_groups: fixture.expected }).instructionGroups, fixture.expected);
  assert.deepEqual(new PrepTaskPresentation({ ...fixture.task, instruction_groups: [] }).instructionGroups, []);
});

const mealFixture = JSON.parse(readFileSync(new URL("../../tests/fixtures/prep_meal_groups.json", import.meta.url)));

test("by-meal fallback matches the shared contract and preserves source", () => {
  const tasks = structuredClone(mealFixture.tasks);
  assert.deepEqual(prepMealGroups({ tasks }), mealFixture.expected);
  assert.deepEqual(tasks, mealFixture.tasks);
});

test("server meal groups are authoritative, including an empty result", () => {
  assert.deepEqual(prepMealGroups({ tasks: mealFixture.tasks, meal_groups: mealFixture.expected }), mealFixture.expected);
  assert.deepEqual(prepMealGroups({ tasks: mealFixture.tasks, meal_groups: [] }), []);
});
