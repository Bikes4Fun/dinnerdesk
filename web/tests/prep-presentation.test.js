import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { PrepTaskPresentation } from "../src/PrepTaskPresentation.js";

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
