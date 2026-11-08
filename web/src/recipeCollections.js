// The recipe lists every Recipes screen shows, built one way. iOS (RecipeCollections in
// Models.swift) and Android (RecipeCollections.kt) have the same class with the same members and
// rules, so the three apps always group and filter recipes alike.
//
// Coming-soon recipes (our photo, steps not written yet) stay out of every themed list; they have
// their own list and come last in "all".

export function isExtra(r) {
  const tags = r.tags || [];
  if (tags.includes("main_dish") || tags.includes("full_meal")) return false;
  return tags.some((t) => t === "sauce" || t === "dressing" || t === "component");
}

// Salt, oil and water don't count toward a recipe's ingredient count.
const STAPLE = /^(salt|black pepper|pepper|olive oil|extra virgin olive oil|vegetable oil|neutral cooking oil|canola oil|oil|water|cooking spray)$/;
const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ").replace(/\s+/g, " ").trim();

// Budget friendly: at most 8 ingredients besides staples.
export function isBudget(r) {
  const n = (r.ingredients || []).map(norm).filter((x) => x && !STAPLE.test(x)).length;
  return n > 0 && n <= 8;
}

const byName = (a, b) => a.name.localeCompare(b.name);
const has = (r, tag) => (r.tags || []).includes(tag);

export class RecipeCollections {
  // Search filter chips, in order. Same keys and labels on iOS and Android.
  static FILTERS = [
    ["all", "All"],
    ["pantry", "Uses pantry"],
    ["fav", "Your favorites"],
    ["try", "To try"],
    ["popular", "Popular"],
    ["quick", "Quick"],
    ["hidden", "Hidden"],
    ["soon", "Coming soon"],
  ];

  constructor(recipes) {
    this.recipes = recipes;
    this.ready = recipes.filter((r) => !r.coming_soon);
    this.comingSoon = recipes.filter((r) => r.coming_soon).sort(byName);
    this.favorites = this.ready.filter((r) => r.favorited);
    this.toTry = this.ready.filter((r) => r.to_try);
    this.mine = this.ready.filter((r) => !r.catalog);
    this.meals = this.ready.filter((r) => !isExtra(r));
    this.sauces = this.ready.filter(isExtra);
    this.popular = this.meals.filter((r) => has(r, "popular"));
    this.simple = this.meals.filter((r) => (r.cooking_minutes || 99) <= 20);
    this.budget = this.meals.filter(isBudget);
    // Needs r.usesPantry, set by the page from the kitchen's pantry (same rule as PantryMatch).
    this.pantry = this.meals.filter((r) => r.usesPantry);
    // Every meal A–Z, then the coming-soon ones.
    this.all = [...this.meals].sort(byName).concat(this.comingSoon);
  }

  // `rows` narrowed by the search filters that are on (keys from FILTERS). "hidden" picks the
  // source list and "pantry" needs r.usesPantry, so the page handles those inputs.
  filter(rows, filters) {
    let out = filters.includes("soon") ? rows.filter((r) => r.coming_soon) : rows;
    if (filters.includes("fav")) out = out.filter((r) => r.favorited);
    if (filters.includes("try")) out = out.filter((r) => r.to_try);
    if (filters.includes("popular")) out = out.filter((r) => has(r, "popular"));
    if (filters.includes("pantry")) out = out.filter((r) => r.usesPantry);
    if (filters.includes("quick")) out = out.filter((r) => (r.cooking_minutes || 99) <= 30);
    return out;
  }
}
