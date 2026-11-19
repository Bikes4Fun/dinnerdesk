"""Merge plan ingredients into grocery lines. No I/O."""

from __future__ import annotations

import re
from fractions import Fraction

from .ingredient_review import plural_key
from .ingredients import AISLES, apply_alias, aisle_for, pantry_key
from .pantry_catalog import in_grocery_catalog, ingredient_name

_VULGAR = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

_UNIT_ALIASES = {
    "lb": "lb",
    "lbs": "lb",
    "pound": "lb",
    "pounds": "lb",
    "oz": "oz",
    "ounce": "oz",
    "ounces": "oz",
    "fl oz": "fl oz",
    "fluid oz": "fl oz",
    "fluid ounce": "fl oz",
    "fluid ounces": "fl oz",
    "cup": "cup",
    "cups": "cup",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "clove": "clove",
    "cloves": "clove",
    "head": "head",
    "heads": "head",
    "bunch": "bunch",
    "bunches": "bunch",
    "can": "can",
    "cans": "can",
    "pint": "pint",
    "pints": "pint",
}


# Words a recipe uses to say how an ingredient arrives, as opposed to which one to buy.
# A note made only of these is dropped: "cilantro, chopped" is cilantro. Anything else is
# part of the name, so "beans, black" and "milk, 2%" keep theirs.
_PREP_NOTE_WORDS = frozenset("""
about and at chopped coarsely cooked crumbled crushed cubed cut diced divided drained dried
finely for freshly frozen garnish grated halved into juiced julienned leaves lightly loosely
melted minced more only optional or packed peeled pieces pitted plus quartered rinsed roughly
room seeded served serving shaken shredded sliced slices softened stem stemmed stems strips
taste temperature thawed thickly thinly torn trimmed uncooked washed wedges well zested
""".split())

# Knife work a recipe may put in front of the food. Shelf forms ("crushed tomatoes",
# "shredded mozzarella", "grated parmesan") are deliberately absent from both: those name a
# different product, not a preparation.
_MODIFIER = r"(?:(?:finely|roughly|coarsely|thinly|thickly|freshly|fresh)\s+)*"
# No shop sells these as a product, so dropping them is always safe.
_LEADING_PREP = re.compile(
    rf"^{_MODIFIER}(?:chopped|torn|halved|quartered|peeled|trimmed|stemmed|seeded|cubed"
    r"|julienned)\s+",
    re.I,
)
# These can go either way ("minced garlic" and "sliced almonds" are sold as such), so they
# come off only when the catalog recognizes what's left. "diced" is not here: "diced
# tomatoes" is the canned one, and merging that into fresh tomatoes buys the wrong thing.
_LEADING_PREP_OR_PRODUCT = re.compile(rf"^{_MODIFIER}(?:minced|sliced)\s+", re.I)

_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")
_COMMA_NOTE = re.compile(r"^(?P<name>[^,]+),(?P<note>.*)$", re.S)
_LEADING_FRESH = re.compile(r"^(?:freshly|fresh)\s+", re.I)
_WORD = re.compile(r"[a-z]+")


def _without_prep_note(name: str) -> str:
    """Drop a trailing note that only says how the ingredient is prepared."""
    found = _COMMA_NOTE.match(name)
    if not found:
        return name
    words = _WORD.findall(found.group("note").lower())
    if not words or any(word not in _PREP_NOTE_WORDS for word in words):
        return name
    return found.group("name").strip()


def grocery_names(raw: str) -> list[str]:
    """`raw` and the shorter names it reduces to, longest first.

    How a recipe writes a preparation is not part of what you buy, so "1/4 cup fresh
    cilantro, chopped" and "cilantro" belong on one line (#90).
    """
    names: list[str] = []
    value = raw or ""
    for shorten in (
        lambda v: v,
        lambda v: _PARENTHETICAL.sub(" ", v),
        _without_prep_note,
        lambda v: _LEADING_FRESH.sub("", v),
        lambda v: _LEADING_PREP.sub("", v),
    ):
        value = re.sub(r"\s+", " ", shorten(value)).strip()
        if value and value not in names:
            names.append(value)
    return names


def grocery_name_without_prep(raw: str) -> str:
    """`raw` with a leading word that might be a preparation dropped ("minced garlic").

    Only used when the catalog recognizes the result, since nothing in the wording tells a
    preparation from a product name.
    """
    return re.sub(r"\s+", " ", _LEADING_PREP_OR_PRODUCT.sub("", raw or "")).strip()


def grocery_item_name(raw: str, aliases: dict[str, str], overrides: dict[str, str]) -> str:
    key = apply_alias(raw, aliases)
    canonical = ingredient_name(key)
    # Shorten only while the catalog doesn't recognize the longer name, so a product whose
    # name carries one of these words ("fresh mozzarella") keeps its own identity.
    if not in_grocery_catalog(key):
        shorter_names = grocery_names(key)[1:]
        for shorter in shorter_names:
            canonical = ingredient_name(apply_alias(shorter, aliases))
            if in_grocery_catalog(shorter):
                break
        else:
            # Last resort: drop a leading preparation, but only onto a name the catalog
            # knows, so "crushed tomatoes" can't quietly become tomatoes.
            plain = grocery_name_without_prep(shorter_names[-1] if shorter_names else key)
            if plain and in_grocery_catalog(plain):
                canonical = ingredient_name(apply_alias(plain, aliases))
    key = overrides.get(pantry_key(key), overrides.get(canonical, canonical))
    return ingredient_name(apply_alias(key, aliases))


def _norm_unit(unit: str) -> str:
    u = re.sub(r"\s+", " ", (unit or "").strip().lower().rstrip("."))
    return _UNIT_ALIASES.get(u, u)


def normalize_vulgar(text: str) -> str:
    s = text or ""
    for glyph, frac in _VULGAR.items():
        s = s.replace(glyph, f" {frac} ")
    return re.sub(r"\s+", " ", s).strip()


_PACK_UNIT_RE = re.compile(
    r"^\(\s*[\d\s./]+\s*(?:fl\s*oz|ounces?|oz|pounds?|lbs?|grams?|g|ml)\s*\)\s*"
    r"(?:packages?|pkgs?|pkg|cans?|jars?|bags?|boxes?)?$",
    re.I,
)


def _clean_unit(unit: str) -> str | None:
    u = re.sub(r"\s+", " ", (unit or "").strip())
    u = re.sub(r"\s+of\s+.*$", "", u, flags=re.I).strip()
    if not u:
        return ""
    if re.search(r"\d", u):
        if not _PACK_UNIT_RE.match(u):
            return None
        packed = u.lower()
        packed = re.sub(r"\bpackages?\b", "pkg", packed)
        packed = re.sub(r"\bpkgs?\b", "pkg", packed)
        return packed
    return _norm_unit(u)


def parse_qty(text: str) -> tuple[Fraction, str] | None:
    s = normalize_vulgar(text)
    if not s:
        return None
    s = re.sub(r"^(?:about|approx(?:imately)?)\s+", "", s, flags=re.I)
    m = re.fullmatch(
        r"(\d+)\s+(\d+)\s*/\s*(\d+)(?:\s+(.+))?",
        s,
    )
    if m:
        unit = _clean_unit(m.group(4) or "")
        if unit is None:
            return None
        amt = Fraction(int(m.group(1))) + Fraction(int(m.group(2)), int(m.group(3)))
        return amt, unit
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)(?:\s+(.+))?", s)
    if m:
        unit = _clean_unit(m.group(3) or "")
        if unit is None:
            return None
        return Fraction(int(m.group(1)), int(m.group(2))), unit
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(?:\s+(.+))?", s)
    if not m:
        return None
    unit = _clean_unit(m.group(2) or "")
    if unit is None:
        return None
    return Fraction(m.group(1)), unit


_NUMBER = r"(?:\d+\s+\d+\s*/\s*\d+|\d+\s*/\s*\d+|\d+(?:\.\d+)?)"
# "2", "1 1/2", "about 3", and ranges: "5 to 8", "2-3", "1 or 2".
_AMOUNT_RE = re.compile(
    rf"^(?:about\s+)?{_NUMBER}(?:\s*(?:-|–|to|or)\s*{_NUMBER}(?!\s*%))?",
    re.I,
)
_PAREN_WT_RE = re.compile(
    r"^\(\s*[\d\s./]+\s*(?:fl\s*oz|ounces?|oz|pounds?|lbs?|grams?|g|ml)\s*\)",
    re.I,
)
_UNIT_RE = re.compile(
    r"^(?:fluid\s+ounces?|fl(?:uid)?\s+oz|tablespoons?|teaspoons?|pounds?|ounces?|"
    r"cups?|tbsp|tsp|lbs?|oz|cloves?|heads?|pints?|bunches?|bunch|cans?|"
    r"packages?|pkgs?|pkg|slices?|pinch(?:es)?|dash(?:es)?)\b",
    re.I,
)


def split_ingredient_line(line: str) -> tuple[str, str]:
    """Pull a leading amount/unit off a recipe line. Keep '2% milk' intact."""
    s = normalize_vulgar(re.sub(r"\s+", " ", (line or "").strip()))
    if not s:
        return "", ""
    if re.match(r"^\d+\s*%", s):
        return "", s
    rest = s
    qty_parts: list[str] = []
    m = _AMOUNT_RE.match(rest)
    if m:
        qty_parts.append(m.group(0).strip())
        rest = rest[m.end() :].lstrip()
    m = _PAREN_WT_RE.match(rest)
    if m:
        qty_parts.append(m.group(0).strip())
        rest = rest[m.end() :].lstrip()
    m = _UNIT_RE.match(rest)
    if m:
        qty_parts.append(m.group(0).strip())
        rest = rest[m.end() :].lstrip()
    m = _PAREN_WT_RE.match(rest)
    if m:
        qty_parts.append(m.group(0).strip())
        rest = rest[m.end() :].lstrip()
    if not qty_parts:
        m = _UNIT_RE.match(rest)
        if m and rest[m.end() :].strip():
            return m.group(0).strip(), rest[m.end() :].lstrip()
        return "", s
    if not rest:
        return " ".join(qty_parts), ""
    return " ".join(qty_parts), rest


def _without_repeat(name: str) -> str:
    """Drop a tail that just repeats the food, in either number.

    A row saved as quantity "1/4 cup cilantro" with name "cilantro" used to join into
    "cilantro cilantro", which then sat on its own grocery line (#90).
    """
    words = name.split()
    for size in range(len(words) // 2, 0, -1):
        tail = plural_key(" ".join(words[-size:]).lower())
        before = plural_key(" ".join(words[-2 * size : -size]).lower())
        if tail and tail == before:
            return " ".join(words[:-size])
    return name


def coerce_qty_name(quantity: str, name: str) -> tuple[str, str]:
    """Fix lines saved as quantity '1' + name 'cup yogurt' (or unit-only names)."""
    qty = re.sub(r"\s+", " ", (quantity or "").strip())
    nam = re.sub(r"\s+", " ", (name or "").strip())
    line = f"{qty} {nam}".strip()
    if not line:
        return "", ""
    parsed_qty, parsed_name = split_ingredient_line(line)
    if parsed_name:
        return parsed_qty, _without_repeat(parsed_name)
    if nam:
        return qty, nam
    return parsed_qty, parsed_name


_PLURAL = {
    "cup": "cups",
    "clove": "cloves",
    "bunch": "bunches",
    "can": "cans",
    "pint": "pints",
}


def format_qty(amount: Fraction, unit: str) -> str:
    if amount.denominator == 1:
        num = str(amount.numerator)
    elif amount.denominator in (2, 3, 4, 8):
        whole = amount.numerator // amount.denominator
        rest = amount - whole
        if whole and rest:
            num = f"{whole} {rest.numerator}/{rest.denominator}"
        else:
            num = f"{amount.numerator}/{amount.denominator}"
    else:
        num = f"{float(amount):g}"
    shown = unit
    if unit in _PLURAL and amount > 1:
        shown = _PLURAL[unit]
    return f"{num} {shown}".strip()


def scale_quantity(text: str, factor: Fraction) -> str:
    qty = (text or "").strip()
    if not qty or factor == 1:
        return qty
    parsed = parse_qty(qty)
    if not parsed:
        return qty
    amount, unit = parsed
    return format_qty(amount * factor, unit)


def combine_quantities(parts: list[str]) -> str:
    by_unit: dict[str, Fraction] = {}
    order: list[str] = []
    leftover: list[str] = []
    flat: list[str] = []
    for raw in parts:
        qty = (raw or "").strip()
        if not qty:
            continue
        if " + " in qty:
            flat.extend(bit.strip() for bit in qty.split(" + ") if bit.strip())
        else:
            flat.append(qty)
    for qty in flat:
        parsed = parse_qty(qty)
        if not parsed:
            leftover.append(qty)
            continue
        amount, unit = parsed
        if unit not in by_unit:
            by_unit[unit] = Fraction(0)
            order.append(unit)
        by_unit[unit] += amount
    bits = [format_qty(by_unit[u], u) for u in order]
    bits.extend(leftover)
    return " + ".join(bits)


def merge_grocery(
    slot_ings: list[dict],
    pantry_have: set[str],
    never_shop: set[str],
    aliases: dict[str, str],
    overrides: dict[str, str] | None = None,
) -> list[dict]:
    """slot_ings items: {name, quantity, recipe_id, recipe_name}."""
    swaps = overrides or {}
    grouped: dict[str, dict] = {}
    for row in slot_ings:
        qty, raw = coerce_qty_name(row.get("quantity") or "", row.get("name") or "")
        key = grocery_item_name(raw, aliases, swaps)
        if not key:
            continue
        cur = grouped.get(key)
        if not cur:
            cur = {
                "name": key,
                "quantities": [],
                "meals": [],
                "aisle": aisle_for(key),
            }
            grouped[key] = cur
        if qty:
            cur["quantities"].append(qty)
        rid = row.get("recipe_id")
        rname = row.get("recipe_name") or ""
        existing = next((m for m in cur["meals"] if rid is not None and m.get("id") == rid), None)
        if existing:
            if qty:
                prev = existing.get("quantity") or ""
                existing["quantity"] = combine_quantities([prev, qty] if prev else [qty])
        elif rid is not None or rname:
            cur["meals"].append({"id": rid, "name": rname, "quantity": qty})

    have = {grocery_item_name(n, aliases, swaps) for n in pantry_have}
    staples = {grocery_item_name(n, aliases, swaps) for n in never_shop}
    lines = []
    for key, cur in grouped.items():
        owned = key in have or any(key in h or h in key for h in have if h)
        staple = key in staples
        lines.append(
            {
                "name": key,
                "quantity": combine_quantities(cur["quantities"]),
                "aisle": cur["aisle"],
                "from_pantry": owned,
                "never_shop": staple,
                "checked": staple,
                "used_by": [m["name"] for m in cur["meals"] if m.get("name")],
                "used_in": cur["meals"],
            }
        )
    aisle_order = {aisle: index for index, aisle in enumerate(AISLES)}
    lines.sort(key=lambda x: (aisle_order.get(x["aisle"], 9), x["name"]))
    return lines
