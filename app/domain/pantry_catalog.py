"""Grocery-item pantry names: collapse plurals, aliases, and obvious recipe leftovers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from app.assets import catalog_dir

import re

from app.domain.ingredient_review import ingredient_core, plural_key
from app.domain.ingredients import pantry_key, zone_for

_DATA = catalog_dir()

# Same grocery item. Keys and values are pantry_key form.
# Variety / form aliases only — not singular/plural pairs.
ALIASES = {
    "baby arugula": "arugula",
    "baby spinach": "spinach",
    "basil": "fresh basil",
    "broccoli florets": "broccoli",
    "cauliflower florets": "cauliflower",
    "canola oil": "neutral cooking oil",
    "chicken breasts, boneless skinless": "boneless skinless chicken breasts",
    "chicken thighs, boneless skinless": "boneless skinless chicken thighs",
    "crumbled feta cheese": "feta cheese",
    "chicken wings, split with tips removed": "chicken wings",
    "chunk light tuna in water": "canned tuna",
    "edamame, shelled": "edamame",
    "garbanzo beans": "canned chickpeas",
    "fresh mozzarella": "mozzarella cheese",
    "fresh mozzarella cheese": "mozzarella cheese",
    "green onion": "green onions (scallions)",
    "green onions": "green onions (scallions)",
    "hard-cooked eggs, peeled": "eggs",
    "heavy whipping cream": "heavy cream",
    "italian parsley": "italian (flat-leaf) parsley",
    "jalapeño": "jalapeño peppers",
    "jalapeño pepper": "jalapeño peppers",
    "milk": "2% milk",
    "natural peanut butter": "peanut butter",
    "neutral oil": "neutral cooking oil",
    "neutral vegetable oil": "neutral cooking oil",
    "onion": "yellow onion",
    "oregano, dried": "dried oregano",
    "oven roasted turkey breast, sliced": "sliced turkey breast",
    "parmesan cheese, shredded": "parmesan cheese",
    "pure maple syrup": "maple syrup",
    "raw peeled shrimp, fresh or frozen": "shrimp",
    "crushed red pepper": "red pepper flakes",
    "rosemary, dried": "dried rosemary",
    "rotisserie chicken, white and dark meat": "rotisserie chicken",
    "sage, dried": "dried sage",
    "thyme": "fresh thyme",
    "thyme, dried": "dried thyme",
    "wild pink salmon, traditional style": "canned salmon",
    "yukon gold potatoes": "yellow potatoes",
    "vegetable oil": "neutral cooking oil",
    "zucchini squash": "zucchini",
}


def item_key(name: str) -> str:
    n = re.sub(r"\s+", " ", pantry_key(name).replace("-", " ")).strip()
    return plural_key(n)


# Common grocery items the recipe-derived list missed.
STAPLES = (
    "2% milk",
    "arugula",
    "bread flour",
    "boneless skinless chicken breasts",
    "boneless skinless chicken thighs",
    "canned salmon",
    "canned tuna",
    "chicken wings",
    "dried oregano",
    "dried rosemary",
    "dried sage",
    "dried thyme",
    "fresh basil",
    "fresh thyme",
    "green onions (scallions)",
    "heavy cream",
    "italian (flat-leaf) parsley",
    "maple syrup",
    "peanut butter",
    "red pepper flakes",
    "rotisserie chicken",
    "russet potatoes",
    "shrimp",
    "sliced turkey breast",
    "sour cream",
    "spinach",
    "sweet potatoes",
    "neutral cooking oil",
    "white potatoes",
    "yellow onion",
    "zucchini",
)

STAPLE_NAMES = frozenset(STAPLES)

SKIP = frozenset(
    {
        "aluminum foil",
        "aluminum foil (10x12 inches square)",
        "boiling water (from the pasta)",
        "water",
    }
)


def _load_json_list(path: Path, default):
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        raise
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list in {path}")
    return data


def _without_leading_qty(name: str) -> str:
    """Drop recipe leftovers like '3/4 pound lean ground beef'. Keep '2% milk'."""
    value = pantry_key(name)
    if re.match(r"^\d+\s*%", value):
        return value
    if not re.match(r"^(?:about\s+)?(?:\d|[¼½¾⅓⅔⅛⅜⅝⅞])", value):
        return value
    return ingredient_core(value, False) or value


def canonical_pantry_name(name: str) -> str:
    key = _without_leading_qty(name)
    if not key or key in SKIP or key.startswith("<!") or "<html" in key:
        return ""
    folded = item_key(key)
    for candidate in (key, folded, key.replace("-", " ")):
        if candidate in ALIASES:
            return ALIASES[candidate]
    return key


@lru_cache(maxsize=1)
def _item_preferred() -> dict[str, str]:
    rows = _load_json_list(_DATA / "pantry_catalog.json", [])
    extras = _load_json_list(_DATA / "pantry_extras.json", [])
    return {item_key(name): name for name, _zone in catalog_entries(rows, extras)}


def preferred_grocery_name(raw: str) -> str:
    name = canonical_pantry_name(raw)
    if not name:
        return ""
    return _item_preferred().get(item_key(name), name)


def in_grocery_catalog(raw: str) -> bool:
    name = canonical_pantry_name(raw)
    return bool(name) and item_key(name) in _item_preferred()


def _preferred(names: list[str]) -> str:
    mapped = [canonical_pantry_name(n) for n in names]
    mapped = [n for n in mapped if n]
    if not mapped:
        return ""
    counts = {}
    for n in mapped:
        counts[n] = counts.get(n, 0) + 1
    return min(
        counts,
        key=lambda n: (
            -counts[n],
            0 if n in STAPLE_NAMES else 1,
            0 if "-" in n else 1,
            len(n),
            n,
        ),
    )


def collapse_catalog_names(names: list[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for raw in names:
        name = canonical_pantry_name(raw)
        if not name:
            continue
        key = item_key(name)
        if key not in groups:
            groups[key] = []
            order.append(key)
        if name not in groups[key]:
            groups[key].append(name)
    out = []
    seen = set()
    for key in order:
        name = _preferred(groups[key])
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def catalog_entries(rows: list[dict], extras: list[str]) -> list[tuple[str, str]]:
    names = [row.get("name") or "" for row in rows]
    names.extend(extras)
    names.extend(STAPLES)
    items = []
    for name in collapse_catalog_names(names):
        items.append((name, zone_for(name)))
    return items
