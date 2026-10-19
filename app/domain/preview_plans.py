"""Print suggested plans from the recipe catalog. No database and no server.

    python -m app.domain.preview_plans
    python -m app.domain.preview_plans --user healthy --plans 3 --meals 4
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _catalog() -> Path:
    value = os.environ.get("DINNERDESK_CATALOG_DIR", "").strip()
    if not value:
        guess = Path(__file__).resolve().parents[2].parent / "dd_support/catalog/dinnerdesk/data"
        if guess.is_dir():
            os.environ["DINNERDESK_CATALOG_DIR"] = str(guess)
            return guess
        raise SystemExit("Set DINNERDESK_CATALOG_DIR to the catalog data directory.")
    path = Path(value).expanduser()
    if not path.is_dir():
        raise SystemExit(f"Catalog directory does not exist: {path}")
    return path


def load_recipes(catalog: Path) -> list[dict]:
    recipes = []
    for n, path in enumerate(sorted((catalog / "recipes").glob("*.json")), start=1):
        data = json.loads(path.read_text())
        ingredients = [item.get("name") or "" for item in data.get("ingredients") or [] if isinstance(item, dict)]
        name = data.get("name") or path.stem
        if not name or not ingredients:
            continue
        recipes.append({
            "id": n,
            "keys": [str(n)],
            "name": name,
            "ingredients": ingredients,
            "tags": data.get("tags") or [],
            "cooking_minutes": data.get("cooking_minutes"),
        })
    return recipes


# Preview households. No Taste Lab history. Soft keys rank; a diet blocks.
USERS = {
    "new": {"diets": ["omnivore"], "soft": {}},
    "healthy": {
        "diets": ["omnivore"],
        "soft": {"cuisines": ["healthy"], "protein_more": ["seafood"], "protein_less": ["beef"]},
    },
    "comfort": {
        "diets": ["omnivore"],
        "soft": {"cuisines": ["american"], "protein_less": ["ground chicken", "ground turkey"]},
    },
    "vegan": {"diets": ["vegan"], "soft": {}},
    "unique": {
        "diets": ["omnivore"],
        "soft": {
            "cuisines": ["asian", "curry", "mediterranean"],
            "protein_more": ["seafood", "lamb", "venison", "quail", "duck"],
        },
    },
}


def apply_user(taste, name: str) -> None:
    profile = USERS[name]
    from app.domain.taste_rank import DIET_BLOCKS

    taste.diets = profile["diets"]
    taste.soft = profile["soft"]
    blocks = []
    for diet in profile["diets"]:
        block = DIET_BLOCKS.get(diet)
        if block:
            blocks.append(block)
    taste.blocks = blocks


def _pick(pool, meals, user, learn, pick_meals, plan_ings=None):
    taste = learn([], pool)
    apply_user(taste, user)
    return pick_meals(pool, taste, set(), set(), {}, meals, plan_ings=plan_ings or set())


def suggest_plan(recipes, shown: dict[int, dict], plans: list[set[int]], meals: int, user: str, learn, pick_meals) -> list[dict]:
    """Best plan from meals not yet shown.

    Up to half the meals may be ones already suggested, and only when that scores
    higher. No earlier plan contributes more than 41% of this one.
    """
    from app.domain.suggest import shop_set

    prior = set(shown)
    unused = [recipe for recipe in recipes if recipe["id"] not in prior]
    fresh = _pick(unused, meals, user, learn, pick_meals)
    if not shown or not fresh:
        return fresh
    mixed = _pick(unused + list(shown.values()), meals, user, learn, pick_meals)
    # 41% of a plan, truncated. 4 meals share at most 1, 5 share at most 2, 8 share at most 3.
    per_plan = max(1, int(meals * 0.41))
    from_plan = [0] * len(plans)
    repeats = []
    for row in sorted((row for row in mixed if row["id"] in prior), key=lambda row: row["score"], reverse=True):
        if len(repeats) >= meals // 2:
            break
        homes = [i for i, ids in enumerate(plans) if row["id"] in ids]
        # Already in two plans. A third copy would put the same meal in every suggestion.
        if len(homes) >= 2:
            continue
        if any(from_plan[i] >= per_plan for i in homes):
            continue
        repeats.append(row)
        for i in homes:
            from_plan[i] += 1
    kept = [row for row in mixed if row["id"] not in prior] + repeats
    need = meals - len(kept)
    if need > 0:
        taken = {row["id"] for row in kept}
        have = set()
        for row in kept:
            have |= shop_set(row.get("ingredients") or [], {})
        refill = [recipe for recipe in unused if recipe["id"] not in taken]
        kept += _pick(refill, need, user, learn, pick_meals, plan_ings=have)
    if sum(row["score"] for row in kept) <= sum(row["score"] for row in fresh):
        return fresh
    return kept


# Five plans is enough to compare. More than that is a search over combinations, not another plan.
PLAN_CAP = 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Print suggested plans from the catalog.")
    parser.add_argument("--plans", type=int, default=5)
    parser.add_argument("--meals", type=int, default=4)
    parser.add_argument("--user", choices=sorted(USERS), default="new")
    args = parser.parse_args()
    if args.plans > PLAN_CAP:
        print(f"Capping at {PLAN_CAP} plans.")
        args.plans = PLAN_CAP
    catalog = _catalog()
    from app.domain.taste_rank import learn, pick_meals

    recipes = load_recipes(catalog)
    if not recipes:
        raise SystemExit(f"No recipes in {catalog / 'recipes'}")
    shown: dict[int, dict] = {}
    plans: list[set[int]] = []
    print(f"{len(recipes)} recipes, user {args.user}")
    for number in range(1, args.plans + 1):
        picked = suggest_plan(recipes, shown, plans, args.meals, args.user, learn, pick_meals)
        print(f"\nPLAN {number}")
        if not picked:
            print("  (none)")
            break
        for row in picked:
            again = " (again)" if row["id"] in shown else ""
            print(f"  {row['score']:7.3f}  {row['name']}{again}")
            shown[row["id"]] = row
        plans.append({row["id"] for row in picked})


if __name__ == "__main__":
    main()
