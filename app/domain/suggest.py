"""Rank recipes for a suggested plan. No I/O. Not a trained model — a scorer."""

from __future__ import annotations

from .grocery import grocery_item_name
from .ingredients import pantry_key

# How much each signal adds when a plan is suggested. Higher is stronger.
# A heart on a meal they have also marked cooked.
COOKED_BONUS = 4.2
# The To try tag: they plan to cook this meal.
TO_TRY_BONUS = 3.4
# Every shoppable ingredient already in the pantry. Scaled by how much of the meal that is.
PANTRY_BONUS = 3.0
# Taste Lab thumbs-up on this meal. A heart that has not been cooked uses this same number.
LIKE_BONUS = 2.8
# Every shoppable ingredient already used by another meal on this plan.
REUSE_BONUS = 2.2
# Passed straight into score_recipe as a favorite. The suggester does not use this.
# A heart goes through LIKE_BONUS instead.
FAVORITE_BONUS = 1.6
# They approved a Taste Lab suggested plan that included this meal. Not the To try tag.
PLAN_BONUS = 1.4
# Every shoppable ingredient that is not in the pantry and not already on this plan.
NEW_SHOP_PENALTY = 1.4
# A different ingredient in the same role as one they liked, such as pasta lifting polenta.
SIBLING_BONUS = 0.45
# Cosine to the meals they liked, after this floor. Unrelated meals sit around 0.2.
NEIGHBOR_FLOOR = 0.30
# Scales that closeness. A nearby meal stays under a direct thumbs-up.
NEIGHBOR_BONUS = 4.0
# Recipe is tagged popular.
POPULAR_BONUS = 0.35

# Taste evidence and contextual plan feedback. Keep all tuning in this module.
COOKED_WEIGHT = 2.0
LIKE_WEIGHT = 1.0
PLAN_WEIGHT = 0.5
INGREDIENT_SCALE = 6.0
INGREDIENT_REASON = 0.12
OVER_TIME = 1.1
UNDER_TIME = 0.25
PLAN_REFUSAL_PENALTY = 0.75
SWAP_PENALTY = 1.5
APPROVED_SWAP_PENALTY = 3.0
CONTEXT_PENALTY_CAP = 12.0
APPROVAL_RECOVERY = 2.0

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
    }
)


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
) -> tuple[float, list[str]]:
    if not shop:
        score = 0.4 if favorited else 0.1
        reasons = ["simple"]
        if to_try:
            score += TO_TRY_BONUS
            reasons.append("to try")
        return (score, reasons)
    pantry_hit = shop & pantry
    plan_hit = shop & plan_ings
    new_shop = shop - pantry - plan_ings
    pantry_frac = len(pantry_hit) / len(shop)
    reuse_frac = len(plan_hit) / len(shop)
    new_frac = len(new_shop) / len(shop)
    score = pantry_frac * PANTRY_BONUS + reuse_frac * REUSE_BONUS - new_frac * NEW_SHOP_PENALTY
    if favorited:
        score += FAVORITE_BONUS
    if to_try:
        score += TO_TRY_BONUS
    if popular:
        score += POPULAR_BONUS
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
) -> list[dict]:
    """Greedy: each pick updates the plan's ingredient pool so add-ons reuse groceries.

    adjust(recipe) may return (bonus, reasons, reject). Rejected recipes are skipped.
    """
    remaining = list(recipes)
    pool = set(plan_ings)
    trying = to_try or set()
    picked = []
    while remaining and len(picked) < want:
        best = None
        best_key = None
        for rec in remaining:
            shop = shop_set(rec.get("ingredients") or [], aliases, overrides, skip)
            favorited = rec["id"] in favorites
            on_try = rec["id"] in trying
            popular = "popular" in (rec.get("tags") or [])
            score, reasons = score_recipe(shop, pantry, pool, favorited, popular, on_try)
            if adjust:
                bonus, extra, reject = adjust(rec)
                if reject:
                    continue
                score += bonus
                reasons = extra + reasons
            key = (score, 1 if on_try else 0, 1 if favorited else 0, -len(shop))
            if best is None or key > best_key:
                best = {**rec, "score": round(score, 3), "reasons": reasons, "shop": shop}
                best_key = key
        if best is None:
            break
        picked.append(best)
        pool |= best["shop"]
        remaining = [r for r in remaining if r["id"] != best["id"]]
    for row in picked:
        row.pop("shop", None)
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
