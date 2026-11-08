"""Which catalog recipes the app may offer.

Pizza, snacks, and breakfast stay in the catalog files for later. They are not loaded.
A rewritten recipe that does not yet have a photo of ours is coming soon: the recipes
list may show that photo, and it is not a meal anywhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

_BREAKFAST = re.compile(
    r"frittata|omelet|quiche|pancake|waffle|oatmeal|porridge|granola|french toast|breakfast",
    re.I,
)
_PIZZA = re.compile(r"pizza", re.I)
_NACHO = re.compile(r"nachos?", re.I)
# The dish itself, not a dinner that happens to include one ("steak with mango salsa").
_SNACK_TITLE = frozenset({"guacamole", "hummus", "salsa", "pico de gallo", "queso"})

# Lowercase ILIKE patterns. "omelet" also matches "omelette".
WITHHELD_LIKE = (
    "%pizza%",
    "%frittata%",
    "%omelet%",
    "%quiche%",
    "%pancake%",
    "%waffle%",
    "%oatmeal%",
    "%porridge%",
    "%granola%",
    "%french toast%",
    "%breakfast%",
    "%nacho%",
)
WITHHELD_EXACT = tuple(sorted(_SNACK_TITLE))


def withheld(name: str, tags: list | None = None) -> bool:
    """True for pizza, a snack, or breakfast. The catalog file is kept."""
    title = (name or "").strip()
    if _PIZZA.search(title) or _BREAKFAST.search(title) or _NACHO.search(title):
        return True
    main = re.split(r"\s+with\s+", title.lower(), maxsplit=1)[0].strip()
    if main in _SNACK_TITLE:
        return True
    for tag in tags or []:
        if str(tag).strip().lower() in {"snack", "breakfast"}:
            return True
    return False


def offer_photo(data: dict, photos: dict[str, list[str]] | None = None) -> bool:
    """True when the recipe has a photo the app is allowed to show."""
    photo = (data.get("photo_path") or "").strip()
    if not photo:
        return False
    if photos is None:
        return True
    return Path(photo).name in (photos.get("*") or [])


def coming_soon(data: dict, photos: dict[str, list[str]] | None = None) -> bool:
    """Our recipe, kept for later, with no photo yet. Not pizza, snack, or breakfast."""
    if data.get("retired") or data.get("instructions_copied_from_third_party"):
        return False
    if withheld(str(data.get("name") or ""), data.get("tags")):
        return False
    return not offer_photo(data, photos)
