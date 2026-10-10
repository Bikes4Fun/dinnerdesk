"""Search helpers. Recipes ignore protein words; grocery names keep them."""

from __future__ import annotations

import re
import unicodedata

STOP = {
    "a",
    "an",
    "and",
    "the",
    "with",
    "or",
    "of",
    "in",
    "for",
    "on",
    "to",
}

SOFT = {
    *STOP,
    "beef",
    "turkey",
    "chicken",
    "pork",
    "steak",
    "ham",
    "lamb",
    "shrimp",
    "salmon",
    "tofu",
    "veggie",
    "vegetarian",
    "vegan",
    "bean",
    "beans",
    "lentil",
    "lentils",
}


def tokens(text: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split() if t]


def hard_tokens(query: str) -> list[str]:
    return [t for t in tokens(query) if t not in SOFT]


def recipe_matches(query: str, name: str, extra: str = "") -> bool:
    q = tokens(query)
    if not q:
        return True
    hay = f"{name} {extra}".lower()
    needed = [t for t in q if t not in SOFT] or q
    return all(t in hay for t in needed)


def _grocery_hay(name: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", (name or "").lower()).strip()


def _grocery_token_hit(hay: str, token: str) -> bool:
    if token in hay:
        return True
    return any(w.startswith(token) or token.startswith(w) for w in hay.split() if w)


def search_grocery_names(names: list[str], query: str, limit: int = 12) -> tuple[list[str], str]:
    ordered = list(dict.fromkeys(n for n in names if n))
    if not ordered:
        return [], "none"
    toks = [t for t in tokens(query) if len(t) > 1 and t not in STOP]
    if not toks:
        return ordered[:limit], ""
    scored = []
    phrase = " ".join(toks)
    for name in ordered:
        hay = _grocery_hay(name)
        words = hay.split()
        hits = 0
        score = 0
        for t in toks:
            if not _grocery_token_hit(hay, t):
                continue
            hits += 1
            score += 4
            if hay.startswith(t):
                score += 4
            if t in words:
                score += 8
            # The last word names the item: "brown sugar" is sugar, "sugar snap peas" is peas.
            if words and words[-1].startswith(t):
                score += 10
        if hay == phrase:
            score += 40
        if hits:
            scored.append((score, hits, len(words), name))
    scored.sort(key=lambda row: (-row[0], row[2], row[3]))
    scored = [(score, hits, name) for score, hits, _, name in scored]
    if not scored:
        return ordered[:limit], "ideas"
    needed = len(toks)
    all_hit = [name for _, hits, name in scored if hits == needed]
    if all_hit:
        # Keep related partial matches after exact matches for substitutions.
        related = [name for _, hits, name in scored if hits < needed]
        return (all_hit + related)[:limit], ""
    return [name for _, _, name in scored][:limit], "closest"


def _fold(text: str) -> str:
    """Lowercase without accents: "Jalapeño" → "jalapeno"."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def _forms(word: str) -> set[str]:
    """A query word and its singular forms: tomatoes → tomato, strawberries → strawberry."""
    out = {word}
    if len(word) > 4 and word.endswith("ies"):
        out.add(word[:-3] + "y")
    if len(word) > 4 and word.endswith("oes"):
        out.add(word[:-2])
    if len(word) > 3 and word.endswith("es"):
        out.add(word[:-2])
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        out.add(word[:-1])
    return out


def filter_item_matches(names: list[str], query: str, limit: int = 40) -> list[str]:
    """Foods for a custom allergy or avoid (#85). Every query word must match a word of the
    name: its start ("pep" → pepper), a singular form ("tomatoes" → tomato), or, for longer
    words, inside a compound ("berries" → blueberries). Accents don't matter. Best first:
    the exact food, then names that start with it, then shorter names. Never invents a food."""
    words = re.findall(r"[a-z0-9]+", _fold(query))
    if not words:
        return []
    wanted = [_forms(w) for w in words]
    exact = {" ".join(words), " ".join(min(forms, key=len) for forms in wanted)}

    def hit(forms: set[str], part: str) -> bool:
        return any(part.startswith(f) or (len(f) >= 5 and f in part) for f in forms)

    scored = []
    for name in dict.fromkeys(names):
        hay = re.findall(r"[a-z0-9]+", _fold(name))
        if not hay or not all(any(hit(forms, part) for part in hay) for forms in wanted):
            continue
        folded = " ".join(hay)
        rank = 0 if folded in exact else 1 if hit(wanted[0], hay[0]) else 2
        scored.append((rank, len(folded), folded, name))
    return [name for *_, name in sorted(scored)][:limit]
