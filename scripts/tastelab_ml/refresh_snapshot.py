"""Refresh an offline Taste Lab snapshot from the Dinnerdesk catalog."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_snapshot(catalog):
    proposals = defaultdict(list)
    for item in read_json(catalog / "recipe_tag_suggestions.json")["suggestions"]:
        if item.get("source") == "ai":
            proposals[item["slug"]].append({
                "dimension": item["dimension"], "tag": item["tag"], "source": item["source"]
            })

    recipes = []
    for path in sorted((catalog / "recipes").glob("*.json")):
        recipe = read_json(path)
        slug = recipe.get("slug")
        if not slug or recipe.get("retired") or recipe.get("provenance", {}).get("retired"):
            continue
        semantic_tags = proposals.get(slug, [])
        recipes.append({
            "id": recipe.get("id") or slug,
            "slug": slug,
            "name": recipe["name"],
            "ingredients": sorted({
                ingredient["name"] for ingredient in recipe.get("ingredients", [])
                if ingredient.get("name")
            }),
            "tags": sorted({item["tag"] for item in semantic_tags}),
            "semantic_tags": semantic_tags,
        })
    return {"exported_at": datetime.now(timezone.utc).isoformat(), "recipes": recipes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    snapshot = build_snapshot(args.catalog)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    recipes = snapshot["recipes"]
    print(f"{len(recipes)} recipes, {sum(bool(recipe['tags']) for recipe in recipes)} with AI tags")


if __name__ == "__main__":
    main()
