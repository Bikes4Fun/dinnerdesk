"""Print suggested plans from the recipe catalog. No database and no server.

    python -m app.domain.preview_plans
    python -m app.domain.preview_plans --plans 5 --meals 4
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Print suggested plans from the catalog.")
    parser.add_argument("--plans", type=int, default=5)
    parser.add_argument("--meals", type=int, default=4)
    args = parser.parse_args()
    catalog = _catalog()
    from app.domain.taste_rank import learn, pick_meals

    recipes = load_recipes(catalog)
    if not recipes:
        raise SystemExit(f"No recipes in {catalog / 'recipes'}")
    used: set[int] = set()
    print(f"{len(recipes)} recipes")
    for number in range(1, args.plans + 1):
        pool = [recipe for recipe in recipes if recipe["id"] not in used]
        taste = learn([], pool)
        taste.diets = ["omnivore"]
        picked = pick_meals(pool, taste, set(), set(), {}, args.meals)
        print(f"\nPLAN {number}")
        if not picked:
            print("  (none)")
            break
        for row in picked:
            print(f"  {row['score']:7.3f}  {row['name']}")
            used.add(row["id"])


if __name__ == "__main__":
    main()
