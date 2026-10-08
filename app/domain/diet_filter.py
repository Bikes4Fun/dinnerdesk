"""Hard diet and avoid filters for browsing recipes. No I/O.

Uses the same word lists as suggestions (taste_rank), so a meal hidden from Recipes is
also never suggested. Diets are hard rules (vegan, vegetarian, …); avoids are the
kitchen's allergies and dislikes from Settings → What to eat.
"""

from __future__ import annotations

import re

from .taste_rank import AVOID_ALIAS, DIET_BLOCKS, KEYS, hits, recipe_text

# Diets that rule each other out. Picking one clears the others in Settings.
EXCLUSIVE_DIETS = ("omnivore", "pescatarian", "vegetarian", "vegan")

# Meat words the shared list misses. Added for every diet that blocks meat.
MORE_MEAT = [
    "chorizo", "pepperoni", "salami", "pancetta", "veal", "duck", "venison",
    "bison", "meatball", "hot dog", "bratwurst", "kielbasa", "andouille",
    "gelatin", "lard",
]

# Plant-based phrases that contain a blocked word ("butter", "milk", "cream", "beef").
# They are removed before matching so a vegan or dairy-free kitchen still sees them.
PLANT_PHRASES = [
    "peanut butter", "almond butter", "cashew butter", "sunflower butter", "nut butter",
    "apple butter", "cocoa butter", "butternut", "butter lettuce", "butter bean",
    "coconut milk", "almond milk", "oat milk", "soy milk", "rice milk", "cashew milk",
    "coconut cream", "cream of tartar", "coconut yogurt", "beefsteak tomato",
]
# "vegan sausage", "plant-based chicken", "dairy-free cheese": the label and the next word go.
PLANT_LABEL = re.compile(r"\b(?:vegan|plant[- ]based|dairy[- ]free|egg[- ]free|meatless|meat[- ]free)\s+[a-z]+")


def _clean(blob: str) -> str:
    blob = PLANT_LABEL.sub(" ", blob)
    for phrase in PLANT_PHRASES:
        blob = blob.replace(phrase, " ")
    return blob


def blocks_for(diets: list[str] | None, avoids: list[str] | None) -> list[list[str]]:
    """Word groups a recipe must not contain, from the kitchen's diets and avoids."""
    groups: list[list[str]] = []
    for raw in diets or []:
        diet = str(raw).strip().lower()
        block = DIET_BLOCKS.get(diet)
        if not block:
            continue
        if any(word in block for word in KEYS["meat"]):
            block = [*block, *MORE_MEAT]
        groups.append(block)
    for raw in avoids or []:
        key = str(raw).strip().lower()
        if not key or key == "none":
            continue
        key = AVOID_ALIAS.get(key, key)
        if key in KEYS:
            groups.append(KEYS[key])
        elif len(key) >= 3:
            groups.append([key])
    return groups


def allowed(name: str, ingredients: list[str], groups: list[list[str]]) -> bool:
    """True when no blocked word appears in the recipe name or its ingredients."""
    if not groups:
        return True
    blob = _clean(recipe_text(name or "", [i for i in ingredients if i]))
    return not any(hits(blob, group) for group in groups)


def normalize_diets(diets: list[str] | None) -> list[str]:
    """Keep at most one of omnivore / pescatarian / vegetarian / vegan (the last one picked).

    Other diets (gluten-free, dairy-free) combine freely. Omnivore blocks nothing.
    """
    out: list[str] = []
    exclusive: str | None = None
    for raw in diets or []:
        diet = str(raw).strip().lower()
        if not diet:
            continue
        if diet in EXCLUSIVE_DIETS:
            exclusive = diet
        elif diet not in out:
            out.append(diet)
    if exclusive:
        out.insert(0, exclusive)
    return out
