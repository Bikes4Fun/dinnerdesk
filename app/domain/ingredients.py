"""Canonical ingredient names and grocery aisles."""

from __future__ import annotations

import re
import unicodedata

AISLES = ("produce", "dairy", "meat", "pantry", "other")

# Checked in order; the first match wins. Shelf-stable forms come before the
# fresh words they contain ("garlic powder", "tomato paste", "fish sauce").
_FROZEN = re.compile(r"\bfrozen\b")
_FRESH = re.compile(r"\bfresh\b")
_SHELF = re.compile(
    r"\b(?:broth|stock|bouillon|soup|powder|seasoning|spice|flakes|granules|granulated|"
    r"dried|sun-?dried|sundried|(?<!veggie )ground(?!\s+(?:beef|pork|turkey|chicken|lamb))|extract|"
    r"oil|spray|vinegar|vinaigrette|dressing|(?<!tzatziki )sauce|marinara|salsa|pesto|ketchup|mustard|"
    r"mayo|mayonnaise|sriracha|siracha|sambal|chili crisp|aminos|hoisin|worcestershire|"
    r"liquid smoke|canned|cans?|jars?|drained|diced tomatoes|crushed tomatoes|pur[eé]e|"
    r"pasta|noodles?|spaghetti|fettuccin[ei]|linguine|orzo|orecchiette|rotini|penne|"
    r"macaroni|bucatini|ravioli|tortellini|gnocchi|couscous|quinoa|rice|oats|polenta|"
    r"flour|meal|cornstarch|starch|baking|yeast|sugar(?! snap)|honey|syrup|cocoa|"
    r"bread|breadcrumbs|crumbs|panko|croutons|tortillas?|tostadas|chips|buns?|rolls|"
    r"pitas?|naan|flatbreads?|muffins|bagel|dough|crackers|"
    r"(?<!green )beans|chickpeas|lentils|olives|capers|pickles?|artichoke|pimentos|"
    r"almonds?(?! milk)|walnuts|pecans?|cashews|peanuts|pistachios|pine nuts|seeds|nut butter|"
    r"peanut butter|almond butter|coconut milk|coconut cream|cranberries|raisins|"
    r"tuna|sardines|anchov(?:y|ies)|spam|pork rinds|wine|water|salt|"
    r"cumin|paprika|cayenne|turmeric|cinnamon|nutmeg|coriander|garam masala|curry|"
    r"chili powder|bay leaves|5 spice|five spice|everything bagel|bbq rub|roasted red (?:bell )?peppers)\b"
    r"|(?<!garlic )(?<!ginger )\bpaste\b|\bmiso\b|\bgochujang\b|\bprotein powder\b|^oregano$"
)
_PEPPER_SPICE = re.compile(
    r"\b(?:black|white|cayenne|ground)\s+peppers?\b|^peppers?(?:corns?)?$|^pepper\b.*\btaste\b"
)
_MEAT = re.compile(
    r"chicken|steak|beef|pork|turkey|shrimp|salmon|fish|bacon|sausage|lamb|ham\b|"
    r"prosciutto|pepperoni|hot dogs|hamburger|meatballs|ribs\b|halibut|\bcod\b|"
    r"scallops|plant.based|veggie (?:burger|ground)"
)
_DAIRY = re.compile(
    r"\bbutter\b|cheese|\beggs?\b|feta|milk|parmesan|mozzarella|cheddar|ricotta|"
    r"yogurt|cream|crema|half and half|ghee|tzatziki"
)
_PRODUCE = re.compile(
    r"asparagus|avocado|basil|\bbell\b|broccoli|carrot|cilantro|\bcorn\b|cucumber|"
    r"garlic|greens|herbs?\b|jalape|kale|lemon|lettuce|romaine|arugula|spring mix|lime|mint|"
    r"mushroom|onion|scallion|shallot|leek|chive|parsley|\bpeppers?\b|poblano|potato|"
    r"radish|rosemary|thyme|sage|dill|oregano|spinach|chard|bok choy|squash|zucchini|"
    r"eggplant|tomato|cabbage|slaw|celery|ginger|cauliflower|brussels|beets?\b|turnip|"
    r"fennel|green beans|snap peas|\bpeas\b|edamame|sprouts|"
    r"apple|banana|berr|cherr|grape|kiwi|mango|orange|peach|pears?\b|plum|apricot|"
    r"pineapple|dates|tofu|hummus|guacamole|pico de gallo|kimchi"
)


def pantry_key(name: str) -> str:
    return " ".join(unicodedata.normalize("NFC", name or "").casefold().split())


def apply_alias(name: str, aliases: dict[str, str]) -> str:
    key = pantry_key(name)
    return aliases.get(key, key) or key


def aisle_for(name: str) -> str:
    n = pantry_key(name)
    if _FROZEN.search(n):
        return "other"
    if _FRESH.search(n) and _PRODUCE.search(n):
        return "produce"
    if re.search(r"lettuce", n):
        return "produce"
    if _SHELF.search(n) or _PEPPER_SPICE.search(n):
        return "pantry"
    if _MEAT.search(n):
        return "meat"
    if _DAIRY.search(n):
        return "dairy"
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
