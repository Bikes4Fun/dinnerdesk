"""Cuisine and style categories for recipes, from the name and ingredients. No I/O.

Groundwork for letting a kitchen like or dislike whole categories ("more curry", "no
Mexican"). Nothing uses this yet: what a like or dislike does is still to be decided, and
applying it to suggestions belongs to the ranker (taste_rank / suggest).

A recipe can be in several categories (a curry soup is Curry and Soups). The name counts
most; ingredients only count when they're a strong sign (garam masala, tortillas), not
things every kitchen uses (onion, chili powder).
"""

from __future__ import annotations

import re

# key: (label, words in the recipe name, strong signs in the ingredients)
CATEGORIES: dict[str, tuple[str, list[str], list[str]]] = {
    "curry": (
        "Curry & Indian",
        ["curry", "curried", "tikka", "masala", "korma", "dal", "dahl", "daal", "tandoori", "biryani",
         "vindaloo", "chana", "paneer", "saag", "naan", "butter chicken"],
        ["garam masala", "curry powder", "curry paste", "red curry", "green curry", "paneer",
         "naan", "tandoori"],
    ),
    "mexican": (
        "Mexican & Tex-Mex",
        ["taco", "burrito", "enchilada", "fajita", "quesadilla", "nacho", "tostada", "carnitas",
         "chipotle", "mexican", "tex-mex", "elote", "salsa", "pico de gallo", "guacamole",
         "taquito", "chimichanga", "chili con carne", "huevos rancheros", "tortilla soup"],
        ["tortilla", "taco seasoning", "salsa", "chipotle", "enchilada sauce", "queso fresco",
         "cotija", "refried beans", "pico de gallo"],
    ),
    "asian": (
        "Asian stir-fries & noodles",
        ["stir fry", "stir-fry", "teriyaki", "fried rice", "lo mein", "chow mein", "pad thai",
         "ramen", "udon", "soba", "pho", "banh mi", "bulgogi", "bibimbap", "kimchi", "egg roll",
         "dumpling", "potsticker", "sesame", "thai", "korean", "chinese", "japanese",
         "vietnamese", "kung pao", "general tso", "orange chicken", "katsu", "poke", "satay",
         "hoisin", "miso", "bok choy", "szechuan", "sichuan", "gochujang"],
        ["soy sauce", "fish sauce", "hoisin", "sesame oil", "rice vinegar", "gochujang",
         "miso", "sriracha", "rice noodles", "bok choy", "oyster sauce", "mirin"],
    ),
    "italian": (
        "Italian & pasta",
        ["pasta", "spaghetti", "penne", "linguine", "fettuccine", "rigatoni", "orzo", "lasagna",
         "risotto", "gnocchi", "ravioli", "tortellini", "marinara", "pesto", "alfredo",
         "bolognese", "carbonara", "italian", "caprese", "piccata", "marsala", "parmigiana",
         "parmesan chicken", "chicken parm", "bruschetta", "pizza", "calzone", "cacciatore",
         "ziti", "rotini", "farfalle", "tuscan"],
        ["spaghetti", "penne", "linguine", "fettuccine", "rigatoni", "lasagna noodles",
         "marinara", "pesto", "gnocchi", "ricotta", "orzo", "rotini", "farfalle"],
    ),
    "mediterranean": (
        "Mediterranean",
        ["greek", "mediterranean", "tzatziki", "hummus", "falafel", "shawarma", "gyro", "kebab",
         "kabob", "souvlaki", "tabbouleh", "za'atar", "zaatar", "harissa", "moroccan",
         "lebanese", "turkish", "shakshuka", "pita", "halloumi", "couscous"],
        ["tzatziki", "hummus", "za'atar", "zaatar", "harissa", "pita", "kalamata", "halloumi",
         "tahini", "couscous", "sumac"],
    ),
    "comfort": (
        "Comfort classics",
        ["meatloaf", "pot roast", "mashed potato", "mac and cheese", "mac & cheese",
         "macaroni and cheese", "steak and potato", "steak & potato", "casserole", "pot pie",
         "shepherd's pie", "shepherds pie", "cottage pie", "dumplings", "sloppy joe", "burger",
         "fried chicken", "chicken fried steak", "biscuits", "gravy", "salisbury steak",
         "grilled cheese", "pork chop", "meatball", "chicken and rice", "beef stroganoff",
         "stroganoff", "brisket", "bbq", "barbecue", "pulled pork", "baked potato",
         "chicken tenders", "hot dog", "cheesy"],
        [],
    ),
    "healthy": (
        "Healthy & light",
        ["salad", "bowl", "low carb", "low-carb", "cauliflower rice", "zucchini noodle",
         "zoodle", "lettuce wrap", "quinoa", "poke", "grain bowl", "buddha", "skinny",
         "egg white"],
        ["cauliflower rice", "quinoa", "zucchini noodles", "spiralized"],
    ),
    "soups": (
        "Soups & stews",
        ["soup", "stew", "chowder", "bisque", "gumbo", "chili", "pho", "ramen", "minestrone",
         "gazpacho", "pozole", "posole", "goulash", "zuppa", "broth bowl", "dal", "dahl"],
        [],
    ),
}

LABELS = {key: label for key, (label, _, _) in CATEGORIES.items()}
_NAME_WEIGHT = 3
_INGREDIENT_WEIGHT = 1
# Strong ingredient signs needed before ingredients alone put a recipe in a category.
_INGREDIENT_MIN = 2


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(phrase)}(?:e?s)?(?![a-z])", text) is not None


def main_dish(name: str) -> str:
    """The dish itself, without its sides: "Pork Chops with Arugula Salad" → "pork chops"."""
    return re.split(r"\s+with\s+", (name or "").lower(), maxsplit=1)[0]


def categorize(name: str, ingredients: list[str] | None = None) -> list[str]:
    """Category keys for a recipe, strongest first. Only the main dish's name counts."""
    title = main_dish(name)
    ings = [(i or "").lower() for i in ingredients or []]
    scores: dict[str, int] = {}
    for key, (_, name_words, signs) in CATEGORIES.items():
        named = any(_has(title, w) for w in name_words)
        hits = sum(1 for sign in signs if any(_has(i, sign) for i in ings))
        if named or hits >= _INGREDIENT_MIN:
            scores[key] = (_NAME_WEIGHT if named else 0) + hits * _INGREDIENT_WEIGHT
    return sorted(scores, key=lambda k: (-scores[k], list(CATEGORIES).index(k)))


def labels(keys: list[str]) -> list[str]:
    return [LABELS[k] for k in keys if k in LABELS]
