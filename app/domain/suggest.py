"""Rank recipes for a suggested plan. No I/O. Not a trained model — a scorer."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.perf import Laps

from .categories import categorize
from .grocery import grocery_item_name
from .ingredients import pantry_key

@dataclass(frozen=True)
class SuggestionWeights:
    """How much each signal adds when a plan is suggested. Higher is stronger.

    A household can use a different instance later (explore vs favorites, waste vs variety).
    """

    # Taste evidence and contextual plan feedback.
    context_penalty_cap: float = 12.0

    ingredient_scale: float = 6.0

    # A heart on a meal they have also marked cooked.
    cooked_bonus: float = 4.2

    # The To try tag: they plan to cook this meal.
    to_try_bonus: float = 4.0
    
    # Taste Lab thumbs-up on this meal. A heart that has not been cooked uses this same number.
    like_bonus: float = 3.8

    # They approved a Taste Lab suggested plan that included this meal. Not the To try tag.
    plan_bonus: float = 3.4

    # Scales that closeness. A nearby meal stays under a direct thumbs-up.
    neighbor_bonus: float = 3.4

    # Every shoppable ingredient already in the pantry. Scaled by how much of the meal that is.
    pantry_bonus: float = 3.0

    # Every shoppable ingredient already used by another meal on this plan.
    # Meat is left out: a butcher counter sells any amount, so sharing it does not cut waste.
    reuse_bonus: float = 2.2

    cooked_weight: float = 2.0

    approval_recovery: float = 2.0

    # Passed straight into score_recipe as a favorite. The suggester does not use this.
    # A heart goes through like_bonus instead.
    favorite_bonus: float = 1.6

    # Recipe is tagged popular.
    popular_bonus: float = 1.35

    like_weight: float = 1.0

    # Extra bonus per produce, dairy, or fixed can/jar shared across meals.
    # A bunch of cilantro or a pint of cream left from one meal is the waste; meat is not.
    perishable_reuse_bonus: float = 0.5

    plan_weight: float = 0.5

    # A different ingredient in the same role as one they liked, such as pasta lifting polenta.
    sibling_bonus: float = 0.45

    # Cosine to the meals they liked, after this floor. Unrelated meals sit around 0.2.
    neighbor_floor: float = 0.30

    under_time: float = 0.25

    ingredient_reason: float = 0.12

    # Share of the grocery list that is new. An empty pantry is normal, so a meal that
    # needs a full shop loses a little, not as much as a meal they already approved.
    new_shop_penalty: float = -0.35

    plan_refusal_penalty: float = -0.75

    over_time: float = -1.1

    swap_penalty: float = -1.5

    # Each earlier meal in the same category (comfort, seafood, eggs). Bigger than a
    # typical grocery reuse, smaller than a To try meal that also shares ingredients.
    same_kind_penalty: float = -2.5

    approved_swap_penalty: float = -3.0


DEFAULT_WEIGHTS = SuggestionWeights()

STAPLES = frozenset(
    {
        "salt",
        "black pepper",
        "pepper",
        "olive oil",
        "extra virgin olive oil",
        "vegetable oil",
        "neutral cooking oil",
        "canola oil",
        "oil",
        "water",
        "cooking spray",
        "kosher salt",
        "sea salt",
        "white pepper",
        "sugar",
        "granulated sugar",
        "brown sugar",
        "powdered sugar",
        "confectioners sugar",
        "baking powder",
        "baking soda",
        "vanilla extract",
        "cornstarch",
    }
)

# Butcher meat. Bought by the amount requested, so it is not a standard package to use up.
_MEATS = frozenset({
    "chicken", "beef", "pork", "turkey", "lamb", "steak", "salmon", "shrimp", "cod",
    "tilapia", "tuna", "fish", "scallop", "crab", "halibut", "sausage", "bacon", "ham",
})
# Broth and sauce are cans or jars, even when the name includes a meat.
_NOT_BUTCHER = ("broth", "stock", "bouillon", "sauce")

# Produce, dairy, and fixed cans or jars. Matched against normalized shop keys.
# A plan hit on one of these gets perishable_reuse_bonus extra.
_PERISHABLE_KEYWORDS: tuple[str, ...] = (
    "heavy cream", "sour cream", "buttermilk", "cream cheese", "ricotta", "mascarpone",
    "spinach", "kale", "arugula", "swiss chard", "bok choy",
    "coconut milk", "tahini", "miso", "fish sauce", "oyster sauce", "chipotle",
    "sun-dried tomato",
)
# A bunch spoils. The dried jar does not, and an unspecified herb is not assumed fresh.
_FRESH_HERBS: tuple[str, ...] = (
    "cilantro", "parsley", "basil", "mint", "dill", "thyme", "rosemary", "sage", "chives",
)


def _is_meat(key: str) -> bool:
    if any(word in key for word in _NOT_BUTCHER):
        return False
    return bool(set(re.findall(r"[a-z]+", key)) & _MEATS)


def _is_perishable(key: str) -> bool:
    if _is_meat(key):
        return False
    if any(herb in key for herb in _FRESH_HERBS):
        return "fresh" in key and "dried" not in key
    return any(kw in key for kw in _PERISHABLE_KEYWORDS)


def _perishable_hits(ings: set[str]) -> int:
    return sum(1 for ing in ings if _is_perishable(ing))


def meal_kinds(name: str, ingredients: list[str] | None = None) -> frozenset[str]:
    """Category keys such as comfort or seafood, not the words in the title."""
    return frozenset(categorize(name, ingredients))


def scored_name(raw: str, aliases: dict[str, str], overrides: dict[str, str] | None = None) -> str:
    """Same name the grocery list would shop, folded for comparison."""
    return pantry_key(grocery_item_name(raw, aliases, overrides or {}))


def shop_set(
    names: list[str],
    aliases: dict[str, str],
    overrides: dict[str, str] | None = None,
    skip: set[str] | None = None,
) -> set[str]:
    """Ingredients that count toward a suggestion. Staples and never-shop items are left out."""
    skipped = skip or set()
    out = set()
    for raw in names:
        key = scored_name(raw, aliases, overrides)
        if not key or key in STAPLES or key in skipped:
            continue
        out.add(key)
    return out


def score_recipe(
    shop: set[str],
    pantry: set[str],
    plan_ings: set[str],
    favorited: bool,
    popular: bool,
    to_try: bool = False,
    weights: SuggestionWeights = DEFAULT_WEIGHTS,
) -> tuple[float, list[str]]:
    if not shop:
        score = 0.4 if favorited else 0.1
        reasons = ["simple"]
        if to_try:
            score += weights.to_try_bonus
            reasons.append("to try")
        return (score, reasons)
    pantry_hit = shop & pantry
    plan_hit = (shop & plan_ings) - {ing for ing in shop if _is_meat(ing)}
    new_shop = shop - pantry - plan_ings
    shareable = {ing for ing in shop if not _is_meat(ing)}
    pantry_frac = len(pantry_hit) / len(shop)
    reuse_frac = len(plan_hit) / len(shareable) if shareable else 0.0
    new_frac = len(new_shop) / len(shop)
    score = pantry_frac * weights.pantry_bonus + reuse_frac * weights.reuse_bonus + new_frac * weights.new_shop_penalty
    if plan_hit:
        score += _perishable_hits(plan_hit) * weights.perishable_reuse_bonus
    if favorited:
        score += weights.favorite_bonus
    if to_try:
        score += weights.to_try_bonus
    if popular:
        score += weights.popular_bonus
    reasons = []
    if pantry_hit:
        reasons.append(f"uses {len(pantry_hit)} from pantry")
    if plan_hit:
        reasons.append(f"shares {len(plan_hit)} with this plan")
    if to_try:
        reasons.append("to try")
    if favorited:
        reasons.append("favorite")
    if not reasons and not new_shop:
        reasons.append("already covered")
    elif not reasons:
        reasons.append(f"{len(new_shop)} new grocery items")
    return (score, reasons)


def pick_suggestions(
    recipes: list[dict],
    pantry: set[str],
    plan_ings: set[str],
    favorites: set[int],
    aliases: dict[str, str],
    want: int = 5,
    adjust=None,
    overrides: dict[str, str] | None = None,
    skip: set[str] | None = None,
    to_try: set[int] | None = None,
    laps: Laps | None = None,
    weights: SuggestionWeights = DEFAULT_WEIGHTS,
) -> list[dict]:
    """Greedy: each pick updates the plan's ingredient pool so add-ons reuse groceries.

    adjust(recipe, shop) may return (bonus, reasons, reject). Rejected recipes are
    eliminated before the greedy loop; each recipe's static bonus is computed exactly once.
    Only score_recipe (pantry/pool overlap) is recomputed per pick as the pool grows.

    laps, if given, gets "filter" and "greedy" phases and a filtered_out count.
    """
    laps = laps or Laps()
    # Phase 1: pre-compute shop sets and static bonuses; apply hard filters and rejections.
    # Nothing here depends on which meals have already been picked.
    pre: dict[int, tuple[set[str], float, list[str], frozenset[str]]] = {}
    for rec in recipes:
        shop = shop_set(rec.get("ingredients") or [], aliases, overrides, skip)
        if adjust:
            bonus, extra, reject = adjust(rec, shop)
            if reject:
                continue
        else:
            bonus, extra = 0.0, []
        kinds = meal_kinds(rec.get("name") or "", rec.get("ingredients"))
        # Dinner suggestions skip breakfast until a breakfast plan exists.
        if "breakfast" in kinds:
            continue
        pre[rec["id"]] = (shop, bonus, extra, kinds)
    laps.counts["filtered_out"] = len(recipes) - len(pre)
    laps.lap("filter")

    # Phase 2: greedy loop — only score_recipe changes as the pool grows.
    trying = to_try or set()
    pool = set(plan_ings)
    used_kinds: dict[str, int] = {}
    id_to_rec = {rec["id"]: rec for rec in recipes if rec["id"] in pre}
    remaining = list(pre.keys())
    picked = []

    while remaining and len(picked) < want:
        best_id = None
        best_key: tuple | None = None
        best_reasons: list[str] = []
        best_shop: set[str] = set()
        best_kinds: frozenset[str] = frozenset()

        for rid in remaining:
            shop, bonus, extra, kinds = pre[rid]
            rec = id_to_rec[rid]
            favorited = rec["id"] in favorites
            on_try = rec["id"] in trying
            popular = "popular" in (rec.get("tags") or [])
            score, reasons = score_recipe(shop, pantry, pool, favorited, popular, on_try, weights)
            score += bonus
            repeats = sum(used_kinds.get(kind, 0) for kind in kinds)
            if repeats:
                score += weights.same_kind_penalty * repeats
            reasons = extra + reasons
            key = (score, 1 if on_try else 0, 1 if favorited else 0, -len(shop))
            if best_id is None or key > best_key:
                best_id = rid
                best_key = key
                best_reasons = reasons
                best_shop = shop
                best_kinds = kinds

        if best_id is None:
            break

        rec = id_to_rec[best_id]
        picked.append({**rec, "score": round(best_key[0], 3), "reasons": best_reasons})
        pool |= best_shop
        for kind in best_kinds:
            used_kinds[kind] = used_kinds.get(kind, 0) + 1
        remaining.remove(best_id)

    laps.lap("greedy")
    return picked


def norm_pantry(
    names: list[str],
    aliases: dict[str, str],
    overrides: dict[str, str] | None = None,
) -> set[str]:
    out = set()
    for name in names:
        if not name:
            continue
        key = scored_name(name, aliases, overrides)
        if key:
            out.add(key)
    return out
