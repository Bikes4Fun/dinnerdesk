"""Build offline charts from the recipe records used by the Taste Lab scaffold."""

import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path

STAPLES = {
    "salt", "table salt", "kosher salt", "sea salt", "fine sea salt",
    "black pepper", "ground black pepper", "freshly ground black pepper",
    "red pepper flakes", "crushed red pepper", "crushed red pepper flakes",
}


def cooccurrence(recipes, field, min_shared=3):
    """Count each label and pair once per recipe."""
    counts = Counter()
    pairs = defaultdict(list)
    for index, recipe in enumerate(recipes):
        labels = sorted({label.strip().casefold() for label in recipe[field] if label.strip()})
        counts.update(labels)
        for pair in combinations(labels, 2):
            pairs[pair].append(index)

    return {
        "minShared": min_shared,
        "recipes": [recipe.get("name") or str(recipe.get("id", index + 1))
                    for index, recipe in enumerate(recipes)],
        "nodes": [
            dict(name=name, count=count, staple=field == "ingredients" and name in STAPLES)
            for name, count in sorted(counts.items())
        ],
        "links": [
            dict(left=left, right=right, shared=len(indices),
                 lift=len(indices) * len(recipes) / (counts[left] * counts[right]),
                 recipes=indices)
            for (left, right), indices in pairs.items()
        ],
    }


def write_network(recipes, field, output, min_shared):
    population = [recipe for recipe in recipes if recipe["tags"]] if field == "tags" else recipes
    data = cooccurrence(population, field, min_shared)
    encoded = json.dumps(data).replace("<", "\\u003c")
    template = Path(__file__).with_name("network.html").read_text(encoding="utf-8")
    title = "Recipe tag associations" if field == "tags" else "Ingredient associations"
    output.write_text(
        template.replace("__TITLE__", title).replace("__FIELD__", field).replace("__GRAPH__", encoded),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--min-shared", type=int, default=3)
    args = parser.parse_args()
    if args.min_shared < 1:
        parser.error("--min-shared must be at least 1")

    recipes = json.loads(args.data.read_text(encoding="utf-8"))["recipes"]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for field in ("tags", "ingredients"):
        output = args.output_dir / f"{field}.html"
        write_network(recipes, field, output, args.min_shared)
        print(output)


if __name__ == "__main__":
    main()
