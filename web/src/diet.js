// Kitchen diet and avoid choices, shared by Settings → Filters and the Quick start tour.
// The server applies the same rules (app/domain/diet_filter.py) to Recipes and suggestions.

export const DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free"];
export const AVOIDS = ["fish", "shellfish", "peanuts", "cilantro", "spicy"];

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
