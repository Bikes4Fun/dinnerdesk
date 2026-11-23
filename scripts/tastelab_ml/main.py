"""Check the inputs for an offline Taste Lab experiment."""

import argparse
import json
from pathlib import Path


def load_data(path):
    """Read recipe features and swipe labels from one local JSON file."""
    data = json.loads(path.read_text())
    return data["recipes"], data["swipes"]


def prepare_swipes(features, swipes):
    """Join each like or pass to the recipe's current features."""
    return [
        (features[swipe["recipe_id"]], swipe["liked"])
        for swipe in swipes
    ]


def create_features(recipes):
    """Keep ingredient and tag names in separate feature groups."""
    return {
        recipe["id"]: {
            "ingredients": sorted(set(recipe["ingredients"])),
            "tags": sorted(set(recipe["tags"])),
        }
        for recipe in recipes
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data", type=Path, help="Local experiment JSON")
    args = parser.parse_args()

    recipes, swipes = load_data(args.data)
    features = create_features(recipes)
    examples = prepare_swipes(features, swipes)
    print(f"Prepared features for {len(features)} recipes and joined {len(examples)} swipes.")


if __name__ == "__main__":
    main()
