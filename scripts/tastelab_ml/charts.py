"""Build offline charts from the recipe records used by the Taste Lab scaffold."""

import argparse
from collections import Counter
from itertools import combinations
import json
from pathlib import Path

STAPLES = {
    "salt", "table salt", "kosher salt", "sea salt", "fine sea salt",
    "black pepper", "ground black pepper", "freshly ground black pepper",
    "red pepper flakes", "crushed red pepper", "crushed red pepper flakes",
}


def cooccurrence(recipes, field, min_shared=3, links_per_item=5):
    """Count each label and pair once per recipe, then keep the strongest links."""
    counts = Counter()
    pairs = Counter()
    for recipe in recipes:
        labels = sorted({label.strip().casefold() for label in recipe[field] if label.strip()})
        counts.update(labels)
        pairs.update(combinations(labels, 2))

    links = []
    for (left, right), shared in pairs.items():
        if shared >= min_shared:
            lift = shared * len(recipes) / (counts[left] * counts[right])
            if lift > 1:
                links.append(dict(left=left, right=right, shared=shared, lift=lift))

    # Keep a neighborhood for each item, including when staples are hidden.
    selected = {}
    for hide_staples in ([True, False] if field == "ingredients" else [False]):
        degree = Counter()
        for link in sorted(links, key=lambda row: (-row["lift"], -row["shared"], row["left"], row["right"])):
            left, right = link["left"], link["right"]
            if hide_staples and (left in STAPLES or right in STAPLES):
                continue
            if degree[left] >= links_per_item or degree[right] >= links_per_item:
                continue
            selected[left, right] = link
            degree.update((left, right))

    return {
        "nodes": [
            dict(name=name, count=count, staple=field == "ingredients" and name in STAPLES)
            for name, count in sorted(counts.items())
            if field == "tags" or count >= min_shared
        ],
        "links": list(selected.values()),
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
