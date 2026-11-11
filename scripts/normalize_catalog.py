"""Normalize the recipe files themselves, once, so every reader gets the same shape.

    DINNERDESK_CATALOG_DIR=<dd_support>/catalog/dinnerdesk/data \
        python3 scripts/normalize_catalog.py <dd_support> [--dry-run]

Runs app.domain.recipe_normalize.normalize_recipe on every recipe file in
catalog/dinnerdesk/data/recipes, recipes/originals and recipes/rewritten:
amounts split off ingredient names (the grocery list's own parser) and, for recipes whose
steps list no ingredients, each step's ingredients filled in. Files already in shape are
left alone, byte for byte. Line endings are kept.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.recipe_normalize import RecipeNormalizer  # noqa: E402

FOLDERS = ("catalog/dinnerdesk/data/recipes", "recipes/originals", "recipes/rewritten")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", type=Path, help="the dd_support (weekplate) checkout")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    changed = 0
    for folder in FOLDERS:
        for path in sorted((args.repo / folder).rglob("*.json")):
            raw = path.read_bytes()
            try:
                data = json.loads(raw)
            except ValueError:
                print(f"skipped unreadable {path}")
                continue
            if not isinstance(data, dict):
                continue
            new, notes = RecipeNormalizer.normalize(data)
            if not notes:
                continue
            changed += 1
            print(f"{path.relative_to(args.repo)}: {'; '.join(notes)}")
            if not args.dry_run:
                text = json.dumps(new, ensure_ascii=False, indent=2) + "\n"
                if b"\r\n" in raw:
                    text = text.replace("\n", "\r\n")
                path.write_bytes(text.encode("utf-8"))
    print(f"{changed} file(s) {'would change' if args.dry_run else 'changed'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
