"""A household's recipe pool, in two tiers. No I/O.

Hard rules (diets and allergies) are never broken: a recipe that fails them is not in the pool
at all. The priority tier also leaves out recipes with an avoided ingredient, ones the household
hid, and diet variants of a recipe it can already eat. Suggestions, the recipe list and the top
of search results come from the priority tier; the backup tier (everything else that keeps the
hard rules) is used only when the priority tier doesn't have enough.

All of this is evaluated once per household, and again only when its filters or the recipes
change, so no request re-checks every recipe's ingredients. Downvotes (👎 and Taste Lab swipes)
change often and are cheap to apply, so callers apply those per request.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diet_filter import allowed as diet_allowed

# A recipe with a skip tag is a part of a meal, not a dinner, unless it has one of these.
MEAL_TAGS = {"full_meal", "main_dish"}


@dataclass(frozen=True)
class Pool:
    # Every visible recipe that keeps the household's diets and allergies.
    allowed: frozenset[int]
    # Allowed, but has an avoided ingredient or was hidden by the household. Always backup.
    demoted: frozenset[int]
    # Allowed variants of a recipe the household can already eat. Backup, except in a search.
    variants: frozenset[int]
    # Dinner candidates for suggestions, by tier. Both are real meals with ingredients.
    meals: tuple[dict, ...]
    backup_meals: tuple[dict, ...]


def build_pool(recipes: list[dict], hard: list[list[str]], soft: list[list[str]], skip_tags: set[str]) -> Pool:
    """recipes are a household's visible recipes. hard and soft are blocked-word groups.

    A recipe the household wrote itself always keeps the hard rules. A variant (variant_of
    names its base recipe's slug) goes to backup when its base is in the priority tier, so a
    dairy-free kitchen still gets the dairy-free version of a cheesy dish while everyone else
    sees just the original. A variant tagged popular stays in the priority tier.
    """
    def ingredients(r):
        return r.get("filter_ingredients") or r.get("ingredients") or []

    allowed = {r["id"] for r in recipes if r.get("own") or diet_allowed(r.get("name") or "", ingredients(r), hard)}
    kept = [r for r in recipes if r["id"] in allowed]
    avoided = {
        r["id"] for r in kept
        if not r.get("own") and not diet_allowed(r.get("name") or "", ingredients(r), soft)
    }
    priority_slugs = {r["slug"] for r in kept if r.get("slug") and r["id"] not in avoided and not r.get("hidden")}
    variants = {
        r["id"] for r in kept
        if r.get("variant_of") and r["variant_of"] in priority_slugs and "popular" not in (r.get("tags") or [])
    }
    demoted = avoided | {r["id"] for r in kept if r.get("hidden")}
    backup = demoted | variants

    meals, backup_meals = [], []
    for r in kept:
        tags = set(r.get("tags") or [])
        if (tags & skip_tags and not tags & MEAL_TAGS) or not r.get("ingredients"):
            continue
        meal = {k: r[k] for k in ("id", "keys", "name", "ingredients", "tags", "cooking_minutes") if k in r}
        (backup_meals if r["id"] in backup else meals).append(meal)
    return Pool(frozenset(allowed), frozenset(demoted), frozenset(variants), tuple(meals), tuple(backup_meals))


def filters_key(diets: list[str], allergens: list[str], avoids: list[str]) -> tuple:
    """What a pool depends on. A pool built under a different key is out of date."""
    def norm(items):
        return tuple(sorted({str(i).strip().lower() for i in items if str(i).strip()}))
    return norm(diets), norm(allergens), norm(avoids)
