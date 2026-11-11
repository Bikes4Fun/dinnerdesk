// Shared filter choices and per-platform selection adapter.
import { DIETS, ALLERGENS, AVOIDS, WHO, CUISINES, PROTEINS, TIMES, DIET_LABELS, FilterOptions, EXCLUSIVE, STRICTEST } from "./filterOptions.js";
export { DIETS, ALLERGENS, AVOIDS, WHO, CUISINES, PROTEINS, TIMES, DIET_LABELS, FilterOptions };

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
  const picked = STRICTEST.find((d) => diets.includes(d));
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
