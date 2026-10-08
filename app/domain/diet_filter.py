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


# The one list of choices. Settings → Filters, the Quick start tour and Taste Lab all show these
# (web/src/diet.js, tastelab/web/app.js and ios FiltersView copy them; a test keeps them equal).
DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan", "gluten-free", "dairy-free"]
ALLERGENS = ["soy", "peanut", "tree-nuts", "dairy", "egg", "gluten", "sesame", "fish", "shellfish"]
AVOIDS = [
    "fish", "cilantro", "mushrooms", "onions", "bell peppers", "olives", "goat cheese", "nuts",
    "beans", "tofu", "eggplant", "brussels sprouts", "coconut", "spicy",
]
# Older Settings saved these allergies under Avoid.
AVOID_TO_ALLERGEN = {"peanuts": "peanut", "peanut": "peanut", "shellfish": "shellfish"}
STRICTEST = ("vegan", "vegetarian", "pescatarian", "omnivore")


def _words_list(items) -> list[str]:
    out: list[str] = []
    for raw in items if isinstance(items, list) else []:
        word = str(raw).strip().lower()
        if word and word != "none" and word not in out:
            out.append(word)
    return out


def clean_filters(filters: dict | None) -> dict:
    """Household filters in one shape: diets, allergens, avoids (plus time and anything else saved)."""
    out = dict(filters) if isinstance(filters, dict) else {}
    allergens = [AVOID_ALIAS.get(a, a) for a in _words_list(out.get("allergens"))]
    avoids = []
    for word in _words_list(out.get("avoids")):
        if word in AVOID_TO_ALLERGEN:
            allergens.append(AVOID_TO_ALLERGEN[word])
        else:
            avoids.append(word)
    out["diets"] = normalize_diets(_words_list(out.get("diets"))) or ["omnivore"]
    out["allergens"] = list(dict.fromkeys(allergens))
    out["avoids"] = avoids
    return out


def merge_filters(saved: dict | None, patch: dict | None) -> dict:
    """A save from any screen changes only the keys it sends, so the tour can't wipe allergies."""
    base = dict(saved) if isinstance(saved, dict) else {}
    if isinstance(patch, dict):
        base.update(patch)
    return clean_filters(base)


def fold_profiles(filters: dict | None, profiles: list[dict]) -> dict:
    """Add old Taste Lab profiles (diets, allergens, dislikes) to the household filters.

    Nothing is dropped: an allergy set only in Taste Lab must keep blocking meals. For the
    one-of diets the strictest wins.
    """
    out = clean_filters(filters)
    diets = list(out["diets"])
    allergens = list(out["allergens"])
    avoids = list(out["avoids"])
    for prof in profiles:
        if not isinstance(prof, dict):
            continue
        diets.extend(_words_list(prof.get("diets")))
        allergens.extend(_words_list(prof.get("allergens")))
        avoids.extend(_words_list(prof.get("dislikes")))
    strict = next((d for d in STRICTEST if d in diets), None)
    rest = [d for d in diets if d not in STRICTEST]
    out["diets"] = [strict, *rest] if strict else rest
    out["allergens"] = allergens
    out["avoids"] = avoids
    return clean_filters(out)


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
