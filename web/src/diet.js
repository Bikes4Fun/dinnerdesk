// Kitchen diet and avoid choices, shared by Settings → Filters and the Quick start tour.
// The server applies the same rules (app/domain/diet_filter.py) to Recipes and suggestions.

// One filter system: Taste Lab edits these same household filters. Keep the lists equal to
// app/domain/diet_filter.py (tests/test_diet_filter.py checks).
export const DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free"];
export const ALLERGENS = [
  ["soy", "Soy"],
  ["peanut", "Peanut"],
  ["tree-nuts", "Tree nuts"],
  ["dairy", "Dairy"],
  ["egg", "Egg"],
  ["gluten", "Gluten"],
  ["sesame", "Sesame"],
  ["fish", "Fish"],
  ["shellfish", "Shellfish"],
];
export const AVOIDS = [
  "fish", "cilantro", "mushrooms", "onions", "bell peppers", "olives", "goat cheese", "nuts",
  "beans", "tofu", "eggplant", "brussels sprouts", "coconut", "spicy",
];

// Pick one of these; gluten-free and dairy-free combine with it.
const EXCLUSIVE = ["omnivore", "pescatarian", "vegetarian", "vegan"];

/** Tap a diet: switch between the exclusive diets, toggle the others. */
export function toggleDiet(diets, item) {
  if (EXCLUSIVE.includes(item)) {
    if (diets.includes(item)) return diets;
    return [item, ...diets.filter((d) => !EXCLUSIVE.includes(d))];
  }
  return diets.includes(item) ? diets.filter((d) => d !== item) : [...diets, item];
}

/** Older saves could hold several exclusive diets; keep the strictest. */
export function cleanDiets(diets) {
  const picked = ["vegan", "vegetarian", "pescatarian", "omnivore"].find((d) => diets.includes(d));
  const rest = diets.filter((d) => !EXCLUSIVE.includes(d));
  return picked ? [picked, ...rest] : rest;
}

export function toggleAvoid(avoids, item) {
  return avoids.includes(item) ? avoids.filter((x) => x !== item) : [...avoids, item];
}

/** "kale, anchovies" → ["kale", "anchovies"]. */
export function splitOther(raw) {
  return [...new Set(String(raw || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean))];
}

/** Saved words that aren't one of the chips: they go in the Other box. */
export function otherWords(saved, known) {
  const ids = new Set(known.map((k) => (Array.isArray(k) ? k[0] : k)));
  return (saved || []).filter((w) => !ids.has(w));
}
