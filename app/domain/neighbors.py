"""How close two meals are, using Epicure's ingredient map.

Each ingredient is a point from the Epicure co-occurrence embedding. A meal is the
average of its ingredients. A household's likes are the average of the meals they
liked. A candidate scores by its cosine to that average, so one or two Taste Lab
swipes can surface a nearby meal without a hand-written pair list.
"""

from __future__ import annotations

from app.assets import catalog_dir

import json
from array import array
from functools import lru_cache


from .ingredients import pantry_key

DIM = 300
_DIM = DIM
_NAMES: list[str] = json.loads((catalog_dir() / "ingredient_space.json").read_text())
_RAW = array("f")
_RAW.frombytes((catalog_dir() / "ingredient_space.bin").read_bytes())
if len(_RAW) != len(_NAMES) * _DIM:
    raise RuntimeError(
        f"ingredient space has {len(_RAW)} numbers for {len(_NAMES)} ingredients"
    )
_INDEX = {name: i for i, name in enumerate(_NAMES)}
_PHRASES = tuple(sorted(_INDEX, key=len, reverse=True))


def _row(index: int) -> array:
    start = index * _DIM
    return _RAW[start : start + _DIM]


@lru_cache(maxsize=4096)
def epicure_name(name: str) -> str | None:
    """Epicure ingredient for a grocery name. Longest whole-word match wins."""
    key = pantry_key(name).replace("_", " ")
    if not key:
        return None
    if key in _INDEX:
        return key
    padded = f" {key} "
    for phrase in _PHRASES:
        if f" {phrase} " in padded:
            return phrase
    return None


@lru_cache(maxsize=4096)
def meal_vector(names: tuple[str, ...]) -> tuple[float, ...] | None:
    """Unit vector for a meal. `names` is a sorted tuple of shop ingredients."""
    acc = [0.0] * _DIM
    count = 0
    for name in names:
        key = epicure_name(name)
        if key is None:
            continue
        row = _row(_INDEX[key])
        for dim in range(_DIM):
            acc[dim] += row[dim]
        count += 1
    if not count:
        return None
    norm = sum(value * value for value in acc) ** 0.5
    if norm == 0:
        return None
    return tuple(value / norm for value in acc)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return sum(a * b for a, b in zip(left, right))


def unit(total: list[float]) -> tuple[float, ...] | None:
    norm = sum(value * value for value in total) ** 0.5
    if norm == 0:
        return None
    return tuple(value / norm for value in total)
