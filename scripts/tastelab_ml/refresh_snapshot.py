"""Refresh an offline Taste Lab snapshot from the Dinnerdesk catalog."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
import sys
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot(db, catalog):
    proposals = defaultdict(list)
    for item in read_json(catalog / "recipe_tag_suggestions.json")["suggestions"]:
        if item.get("source") == "ai":
            proposals[item["slug"]].append({
                "dimension": item["dimension"], "tag": item["tag"], "source": item["source"]
            })

    recipes = {}
    for row in db.execute(
        """SELECT r.id, r.slug, r.name, r.provenance_json, i.canonical_name
           FROM recipes r
           LEFT JOIN recipe_ingredients ri ON ri.recipe_id = r.id
           LEFT JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE r.household_id IS NULL
           ORDER BY r.id, i.canonical_name"""
    ):
        rid = row["id"]
        if rid not in recipes:
            if json.loads(row["provenance_json"] or "{}").get("retired"):
                continue
            slug = row["slug"]
            semantic_tags = proposals.get(slug, [])
            recipes[rid] = {
                "id": rid,
                "slug": slug,
                "name": row["name"],
                "ingredients": [],
                "tags": sorted({item["tag"] for item in semantic_tags}),
                "semantic_tags": semantic_tags,
            }
        name = row["canonical_name"]
        ingredients = recipes[rid]["ingredients"]
        if name and (not ingredients or ingredients[-1] != name):
            ingredients.append(name)
    return {"exported_at": datetime.now(timezone.utc).isoformat(), "recipes": list(recipes.values())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from app.db.database import connect, database_url

    if not database_url():
        parser.error("Set DATABASE_URL to the Dinnerdesk database to export.")
    db = connect()
    try:
        db.execute("SET TRANSACTION READ ONLY")
        snapshot = build_snapshot(db, args.catalog)
    finally:
        db.close()
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recipes = snapshot["recipes"]
    print(f"{len(recipes)} recipes, {sum(bool(recipe['tags']) for recipe in recipes)} with AI tags")


if __name__ == "__main__":
    main()
