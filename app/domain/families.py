"""Dinner roles for ingredients. A like can nudge a sibling in the same role."""

from __future__ import annotations

from app.assets import catalog_dir

import json


from .ingredients import pantry_key

_BY_NAME: dict[str, str] = {}
for role, names in json.loads((catalog_dir() / "ingredient_families.json").read_text()).items():
    if not isinstance(names, list):
        continue
    for name in names:
        _BY_NAME[pantry_key(str(name))] = role


def family_of(name: str) -> str | None:
    return _BY_NAME.get(pantry_key(name))
