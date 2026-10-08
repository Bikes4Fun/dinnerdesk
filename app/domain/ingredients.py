"""Canonical ingredient names and grocery aisles."""

from __future__ import annotations

import re
import unicodedata

AISLES = ("produce", "dairy", "meat", "pantry", "other")

_MEAT = re.compile(
    r"chicken|steak|beef|pork|turkey|shrimp|salmon|fish|bacon|sausage|lamb"
)
_PRODUCE = re.compile(
    r"asparagus|avocado|basil|bell pepper|broccoli|carrot|cilantro|corn|"
    r"cucumber|garlic|greens|herb|jalape|kale|lemon|lettuce|lime|mint|"
    r"mushroom|onion|parsley|pepper|potato|radish|rosemary|spinach|"
    r"squash|tomato|zucchini|apple|banana|berry|cabbage|celery|ginger"
)
_DAIRY = re.compile(r"butter|cheese|egg|feta|milk|parmesan|yogurt|cream|buttermilk")


def pantry_key(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name or "").casefold().split())


def apply_alias(name: str, aliases: dict[str, str]) -> str:
    key = pantry_key(name)
    return aliases.get(key, key) or key


def aisle_for(name: str) -> str:
    n = pantry_key(name)
    if re.search(r"\b(broth|stock|bouillon)\b", n):
        return "pantry"
    if _MEAT.search(n):
        return "meat"
    if _DAIRY.search(n):
        return "dairy"
    if re.search(r"\b(?:black|white|cayenne|ground)\s+peppers?\b", n) or re.fullmatch(
        r"peppers?(?:corns?)?", n
    ):
        return "pantry"
    if _PRODUCE.search(n):
        return "produce"
    return "pantry"


def zone_for(name: str) -> str:
    n = pantry_key(name)
    if re.search(r"frozen|ice cream", n):
        return "freezer"
    if re.search(r"powder|seasoning|flakes|dried|spice", n):
        return "spices"
    if aisle_for(n) == "produce":
        return "produce"
    if aisle_for(n) == "dairy" or re.search(r"chicken|cilantro", n):
        return "fridge"
    if re.search(r"salt|pepper|oil|spice|garlic|vinegar", n):
        return "spices"
    return "dry"
