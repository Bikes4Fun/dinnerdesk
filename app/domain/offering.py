"""Which catalog recipes the app may offer.

Pizza, snacks, and breakfast stay in the catalog files for later. They are not loaded.
"""

from __future__ import annotations

import re

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
