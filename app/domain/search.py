"""Search helpers. Recipes ignore protein words; grocery names keep them."""

from __future__ import annotations

import re

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
