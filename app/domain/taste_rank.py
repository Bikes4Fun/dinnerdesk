"""Rank meals from Taste Lab likes, passes, and avoid lists. No I/O. Not a trained model.

A meal that fails a hard filter is dropped. The rest get a fixed score. Meals are then
picked greedily, and each pick updates the grocery pool before the next score.
"""

from __future__ import annotations

import re

from .families import family_of
from .neighbors import DIM, cosine, meal_vector, unit
from .suggest import (
    COOKED_WEIGHT, LIKE_WEIGHT, PLAN_WEIGHT, INGREDIENT_SCALE, INGREDIENT_REASON,
    OVER_TIME, UNDER_TIME, PLAN_REFUSAL_PENALTY, SWAP_PENALTY,
    APPROVED_SWAP_PENALTY, CONTEXT_PENALTY_CAP, APPROVAL_RECOVERY,
    COOKED_BONUS,
    LIKE_BONUS,
    NEIGHBOR_BONUS,
    NEIGHBOR_FLOOR,
    PLAN_BONUS,
    SIBLING_BONUS,
    pick_suggestions,
    shop_set,
)

EGG = re.compile(r"(^|[^a-z])eggs?([^a-z]|$)")
BROTH = re.compile(r"chicken or vegetable broth", re.I)

# Same words Taste Lab uses when someone marks a dislike, allergen, or diet.
KEYS = {
    "soy": ["soy", "soya", "tofu", "edamame", "tempeh", "miso"],
    "peanut": ["peanut"],
    "tree-nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "macadamia"],
    "dairy": ["milk", "butter", "cheese", "cream", "yogurt", "yoghurt", "parmesan", "feta", "mozzarella", "cheddar", "whey", "ghee"],
    "egg": ["egg"],
    "gluten": ["wheat", "flour", "bread", "pasta", "spaghetti", "linguine", "penne", "couscous", "panko", "breadcrumb", "soy sauce"],
    "sesame": ["sesame", "tahini"],
    "fish": ["salmon", "tuna", "cod", "halibut", "tilapia", "trout", "anchovy", "fish"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "clam", "mussel", "oyster", "scallop"],
    "cilantro": ["cilantro", "coriander"],
    "mushrooms": ["mushroom"],
    "onions": ["onion"],
    "bell peppers": ["bell pepper"],
    "olives": ["olive"],
    "goat cheese": ["goat cheese", "chèvre", "chevre"],
    "nuts": ["almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "peanut"],
    "beans": ["black bean", "kidney bean", "pinto bean", "white bean", "chickpea", "garbanzo", "lentil", "cannellini"],
    "tofu": ["tofu"],
    "eggplant": ["eggplant"],
    "brussels sprouts": ["brussels sprout", "brussel sprout"],
    "coconut": ["coconut"],
    "meat": ["chicken", "beef", "pork", "turkey", "lamb", "bacon", "sausage", "steak", "ham", "prosciutto"],
    "spicy": ["spicy", "jalapeño", "jalapeno", "sriracha", "chili flake", "cayenne", "hot sauce"],
}
AVOID_ALIAS = {"peanuts": "peanut"}


def _words(*groups: str, extra: tuple[str, ...] = ()) -> list[str]:
    out: list[str] = []
    for group in groups:
        out.extend(KEYS[group])
    out.extend(extra)
    return out


DIET_BLOCKS = {
    "vegan": _words("meat", "fish", "shellfish", "dairy", "egg", extra=("honey",)),
    "vegetarian": _words("meat", "fish", "shellfish"),
    "pescatarian": _words("meat"),
    "gluten-free": _words("gluten"),
    "dairy-free": _words("dairy"),
}


class Taste:
    def __init__(
        self,
        liked: set[str],
        passed: set[str],
        blocks: list[list[str]],
        max_minutes: int | None,
        from_lab: bool,
    ):
        self.liked = liked
        self.passed = passed
        self.plan_liked: set[str] = set()
        self.cooked_liked: set[str] = set()
        self.hearted: set[str] = set()
        self.blocks = blocks
        self.like_ings: dict[str, float] = {}
        self.pass_ings: dict[str, float] = {}
        self.max_minutes = max_minutes
        self.from_lab = from_lab
        self.like_vec: tuple[float, ...] | None = None
        self.pass_vec: tuple[float, ...] | None = None
        self.recipes: list[dict] = []


def recipe_text(name: str, ingredients: list[str]) -> str:
    kept = [item for item in ingredients if item and not BROTH.search(item)]
    return f"{name} {' | '.join(kept)}".lower()


def hits(blob: str, keys: list[str]) -> bool:
    for key in keys:
        if key == "egg":
            if EGG.search(blob):
                return True
        elif key in blob:
            return True
    return False


def _keys(recipe: dict) -> set[str]:
    found = {str(recipe["id"])}
    for key in recipe.get("keys") or []:
        if key is not None and str(key) != "":
            found.add(str(key))
    return found


def _groups(ids: list) -> list[list[str]]:
    groups = []
    for raw in ids:
        key = str(raw).strip().lower()
        if not key:
            continue
        key = AVOID_ALIAS.get(key, key)
        if key in KEYS:
            groups.append(KEYS[key])
        elif len(key) >= 3:
            groups.append([key])
    return groups


def _account(snap: dict, index: int) -> str:
    return str(snap.get("account_id") or snap.get("id") or index)


def _latest_by_account(snapshots: list[dict]) -> list[dict]:
    latest: dict[str, dict] = {}
    for index, snap in enumerate(snapshots):
        if isinstance(snap, dict):
            latest[_account(snap, index)] = snap
    return list(latest.values())


def _lab_votes(snap: dict) -> tuple[dict[str, bool], dict[str, bool]]:
    """Swipe votes, then plan approvals. A swipe on the same meal replaces the plan vote."""
    swipes: dict[str, bool] = {}
    plans: dict[str, bool] = {}
    for swipe in snap.get("swipes") or []:
        if not isinstance(swipe, dict):
            continue
        rid = str(swipe.get("recipe_id") or "")
        if rid:
            swipes[rid] = bool(swipe.get("liked"))
    for plan in snap.get("plans") or []:
        if not isinstance(plan, dict):
            continue
        verdict = plan.get("verdict")
        if verdict not in ("up", "down"):
            continue
        liked = verdict == "up"
        for rid in plan.get("recipe_ids") or []:
            key = str(rid)
            if key and key not in swipes:
                plans[key] = liked
    return swipes, plans


def _votes_by_account(
    snapshots: list[dict],
) -> tuple[dict[str, dict[str, bool]], dict[str, dict[str, bool]]]:
    """Later snapshot wins per meal. A swipe in that snapshot drops the plan vote."""
    swipes: dict[str, dict[str, bool]] = {}
    plans: dict[str, dict[str, bool]] = {}
    for index, snap in enumerate(snapshots):
        if not isinstance(snap, dict):
            continue
        account = _account(snap, index)
        swipe_votes, plan_votes = _lab_votes(snap)
        swipes.setdefault(account, {}).update(swipe_votes)
        kept = plans.setdefault(account, {})
        kept.update(plan_votes)
        for rid in swipe_votes:
            kept.pop(rid, None)
    return swipes, plans


def _marks(by_account: dict[str, dict[str, bool]]) -> dict[str, list[bool]]:
    marks: dict[str, list[bool]] = {}
    for votes in by_account.values():
        for rid, up in votes.items():
            marks.setdefault(rid, []).append(up)
    return marks


def _passed(marks: dict[str, list[bool]]) -> set[str]:
    return {rid for rid, votes in marks.items() if False in votes}


def _liked(marks: dict[str, list[bool]], passed: set[str]) -> set[str]:
    return {rid for rid, votes in marks.items() if rid not in passed and True in votes}


def _filters(snapshots: list[dict], diets: list[str] | None, avoids: list[str] | None):
    lab_diets: set[str] = set()
    dislike_ids: list[str] = []
    allergen_ids: list[str] = []
    for snap in _latest_by_account(snapshots):
        profile = snap.get("profile") if isinstance(snap.get("profile"), dict) else {}
        dislike_ids.extend(str(item) for item in (profile.get("dislikes") or []))
        allergen_ids.extend(str(item) for item in (profile.get("allergens") or []))
        for diet in profile.get("diets") or []:
            lab_diets.add(str(diet).strip().lower())
    household = {str(diet).strip().lower() for diet in (diets or []) if str(diet).strip()}
    blocks = _groups(dislike_ids + allergen_ids + list(avoids or []))
    for diet in lab_diets | household:
        block = DIET_BLOCKS.get(diet)
        if block:
            blocks.append(block)
    return blocks, lab_diets, dislike_ids, allergen_ids


def learn(
    snapshots: list[dict],
    recipes: list[dict],
    *,
    diets: list[str] | None = None,
    avoids: list[str] | None = None,
    max_minutes: int | None = None,
    aliases: dict[str, str] | None = None,
    overrides: dict[str, str] | None = None,
    skip: set[str] | None = None,
) -> Taste:
    """Current filters from each person's latest snapshot. Swipes accumulate across sessions.

    A later swipe on the same meal replaces the earlier one. A pass from anyone drops that meal.
    """
    swipe_accounts, plan_accounts = _votes_by_account(snapshots)
    passed = _passed(_marks(swipe_accounts)) | _passed(_marks(plan_accounts))
    liked = _liked(_marks(swipe_accounts), passed)
    plan_liked = _liked(_marks(plan_accounts), passed | liked)
    blocks, lab_diets, dislike_ids, allergen_ids = _filters(snapshots, diets, avoids)
    from_lab = bool(
        liked or plan_liked or passed or dislike_ids or allergen_ids or (lab_diets - {"omnivore"})
    )
    taste = Taste(liked, passed, blocks, max_minutes, from_lab)
    taste.plan_liked = plan_liked
    taste.recipes = list(recipes)
    _fit(taste, recipes, aliases or {}, overrides or {}, skip or set())
    return taste


def promote(taste: Taste, recipes: list[dict], recipe_ids: set[int]) -> None:
    """A household thumbs-up is the newest word on a meal and replaces an older pass."""
    wanted = {int(rid) for rid in recipe_ids}
    for recipe in recipes:
        if int(recipe["id"]) not in wanted:
            continue
        keys = _keys(recipe)
        taste.passed -= keys
        taste.liked |= keys


def _signal_weight(keys: set[str], taste: Taste) -> tuple[float, float]:
    if keys & taste.passed:
        return 0.0, LIKE_WEIGHT
    if keys & taste.cooked_liked:
        return COOKED_WEIGHT, 0.0
    if keys & taste.liked or keys & taste.hearted:
        return LIKE_WEIGHT, 0.0
    if keys & taste.plan_liked:
        return PLAN_WEIGHT, 0.0
    return 0.0, 0.0


def _shop(recipe: dict, aliases: dict[str, str], overrides: dict[str, str], skip: set[str]) -> set[str]:
    return shop_set(recipe.get("ingredients") or [], aliases, overrides, skip)


def _fit(
    taste: Taste,
    recipes: list[dict],
    aliases: dict[str, str],
    overrides: dict[str, str],
    skip: set[str],
) -> None:
    """Ingredient counts and like/pass centroids from the meals they already judged."""
    like_ings: dict[str, float] = {}
    pass_ings: dict[str, float] = {}
    like = [0.0] * DIM
    passed = [0.0] * DIM
    like_w = 0.0
    pass_w = 0.0
    seen: set[int] = set()
    for recipe in recipes:
        rid = int(recipe["id"])
        if rid in seen:
            continue
        seen.add(rid)
        weight_like, weight_pass = _signal_weight(_keys(recipe), taste)
        if not weight_like and not weight_pass:
            continue
        shop = _shop(recipe, aliases, overrides, skip)
        target = like_ings if weight_like else pass_ings
        weight = weight_like or weight_pass
        for ing in shop:
            target[ing] = target.get(ing, 0.0) + weight
        vec = meal_vector(tuple(sorted(shop)))
        if vec is None:
            continue
        bucket, bucket_w = (like, weight_like) if weight_like else (passed, weight_pass)
        for dim, value in enumerate(vec):
            bucket[dim] += value * bucket_w
        if weight_like:
            like_w += weight_like
        else:
            pass_w += weight_pass
    taste.like_ings = like_ings
    taste.pass_ings = pass_ings
    taste.like_vec = unit(like) if like_w else None
    taste.pass_vec = unit(passed) if pass_w else None


def _apply_household(taste: Taste, recipes: list[dict], favorites: set[int], cooked: set[int]) -> None:
    """A heart counts like a thumbs-up. A heart on a meal they cooked counts for more."""
    by_id = {int(recipe["id"]): recipe for recipe in recipes}
    done = {int(rid) for rid in cooked}
    for rid in favorites:
        recipe = by_id.get(int(rid))
        if not recipe:
            continue
        keys = _keys(recipe)
        if keys & taste.passed:
            continue
        taste.hearted |= keys
        if int(rid) in done:
            taste.cooked_liked |= keys
            taste.liked -= keys
            taste.plan_liked -= keys
        else:
            taste.plan_liked -= keys


def _direct_bonus(keys: set[str], taste: Taste) -> tuple[float, str | None]:
    if keys & taste.cooked_liked:
        return COOKED_BONUS, "you cooked this"
    if keys & taste.liked:
        return LIKE_BONUS, "you liked this"
    if keys & taste.hearted:
        return LIKE_BONUS, "favorite"
    if keys & taste.plan_liked:
        return PLAN_BONUS, "from a plan you approved"
    return 0.0, None


def _ingredient_bonus(shop: set[str], taste: Taste) -> tuple[float, str | None]:
    if not shop or not (taste.like_ings or taste.pass_ings):
        return 0.0, None
    scores = []
    for ing in shop:
        likes = taste.like_ings.get(ing, 0)
        passes = taste.pass_ings.get(ing, 0)
        if likes or passes:
            scores.append((likes + 1) / (likes + passes + 2) - 0.5)
    if not scores:
        return 0.0, None
    mean = sum(scores) / len(scores)
    reason = "similar to meals you liked" if mean > INGREDIENT_REASON else None
    return mean * INGREDIENT_SCALE, reason


def _role_counts(ings: dict[str, float]) -> tuple[dict[str, float], dict[str, str]]:
    totals: dict[str, float] = {}
    example: dict[str, str] = {}
    for name, count in ings.items():
        role = family_of(name)
        if not role:
            continue
        totals[role] = totals.get(role, 0.0) + count
        example.setdefault(role, name)
    return totals, example


def _sibling(shop: set[str], taste: Taste) -> tuple[float, str | None]:
    if not shop or not taste.like_ings:
        return 0.0, None
    likes, example = _role_counts(taste.like_ings)
    passes, _ = _role_counts(taste.pass_ings)
    for ing in shop:
        if taste.like_ings.get(ing):
            continue
        role = family_of(ing)
        if not role:
            continue
        if likes.get(role, 0) > passes.get(role, 0):
            return SIBLING_BONUS, f"another {role}, like the {example[role]} you liked"
    return 0.0, None


def _near(shop: set[str], taste: Taste) -> tuple[float, str | None]:
    liked = taste.like_vec
    if not shop or liked is None:
        return 0.0, None
    vec = meal_vector(tuple(sorted(shop)))
    if vec is None:
        return 0.0, None
    like_cos = cosine(vec, liked)
    passed = taste.pass_vec
    pass_cos = cosine(vec, passed) if passed is not None else 0.0
    if like_cos <= pass_cos:
        return 0.0, None
    gap = like_cos - pass_cos - NEIGHBOR_FLOOR
    if gap <= 0:
        return 0.0, None
    return gap * NEIGHBOR_BONUS, "near a meal you liked"


def _time_bonus(recipe: dict, taste: Taste) -> float:
    minutes = recipe.get("cooking_minutes")
    if not taste.max_minutes or not minutes:
        return 0.0
    if minutes > taste.max_minutes:
        return -OVER_TIME
    return UNDER_TIME


def _reason(reasons: list[str], text: str | None) -> None:
    if text and text not in reasons:
        reasons.append(text)


def _adjust(recipe: dict, taste: Taste, aliases: dict[str, str], overrides: dict[str, str], skip: set[str]):
    keys = _keys(recipe)
    if keys & taste.passed:
        return 0.0, [], True
    blob = recipe_text(recipe.get("name") or "", recipe.get("ingredients") or [])
    for group in taste.blocks:
        if hits(blob, group):
            return 0.0, [], True
    bonus, direct = _direct_bonus(keys, taste)
    bonus -= getattr(taste, "suggestion_penalties", {}).get(int(recipe["id"]), 0.0)
    reasons: list[str] = []
    _reason(reasons, direct)
    shop = _shop(recipe, aliases, overrides, skip)
    ing_bonus, ing_reason = _ingredient_bonus(shop, taste)
    bonus += ing_bonus
    if not reasons:
        _reason(reasons, ing_reason)
    sibling, sibling_reason = _sibling(shop, taste)
    bonus += sibling
    if not reasons:
        _reason(reasons, sibling_reason)
    near, near_reason = _near(shop, taste)
    bonus += near
    _reason(reasons, near_reason)
    bonus += _time_bonus(recipe, taste)
    return bonus, reasons, False


def pick_meals(
    recipes: list[dict],
    taste: Taste,
    pantry: set[str],
    favorites: set[int],
    aliases: dict[str, str],
    want: int,
    overrides: dict[str, str] | None = None,
    skip: set[str] | None = None,
    to_try: set[int] | None = None,
    cooked: set[int] | None = None,
) -> list[dict]:
    swaps = overrides or {}
    ignored = skip or set()
    _apply_household(taste, recipes, favorites, cooked or set())
    known = {int(recipe["id"]): recipe for recipe in taste.recipes}
    for recipe in recipes:
        known[int(recipe["id"])] = recipe
    _fit(taste, list(known.values()), aliases, swaps, ignored)

    def adjust(recipe):
        return _adjust(recipe, taste, aliases, swaps, ignored)

    return pick_suggestions(
        recipes,
        pantry,
        set(),
        set(),
        aliases,
        want,
        adjust,
        swaps,
        ignored,
        to_try,
    )


def suggestion_note(count: int, taste: Taste) -> str:
    if count <= 0:
        return "No meals matched your tastes. Add meals from Recipes."
    noun = "meal" if count == 1 else "meals"
    if taste.from_lab:
        return f"Suggested {count} {noun} from Taste Lab."
    return f"Suggested {count} {noun} from your favorites and pantry."


_LIKED_REASONS = {"you liked this", "favorite", "from a plan you approved"}
_LIKED_PREFIXES = ("similar to meals you liked", "near a meal you liked", "another ")


def reasons_summary(reasons: list[list[str]]) -> str:
    """One short line for the whole plan instead of a line under every meal.

    Each meal counts once per group: cooked before, liked (heart, thumbs-up, approved
    plan, or like a liked meal), to try, and uses pantry food. Empty groups are left out.
    """
    cooked = liked = to_try = pantry = 0
    for lines in reasons:
        if "you cooked this" in lines:
            cooked += 1
        elif any(line in _LIKED_REASONS or line.startswith(_LIKED_PREFIXES) for line in lines):
            liked += 1
        if "to try" in lines:
            to_try += 1
        if any(line.startswith("uses ") and line.endswith(" from pantry") for line in lines):
            pantry += 1
    parts = []
    if cooked:
        parts.append(f"{cooked} you've cooked")
    if liked:
        parts.append(f"{liked} {'matches' if liked == 1 else 'match'} your tastes")
    if to_try:
        parts.append(f"{to_try} to try")
    if pantry:
        parts.append(f"{pantry} {'uses' if pantry == 1 else 'use'} your pantry")
    return " · ".join(parts)


def suggestion_penalties(history: list[dict]) -> dict[int, float]:
    """Repeated refusal lowers rank; targeted swaps, especially in approved plans, weigh more."""
    penalties: dict[int, float] = {}
    for plan in history:
        if plan.get("decision") == "decline":
            for rid in set(plan.get("suggested_recipe_ids", [])):
                penalties[int(rid)] = min(CONTEXT_PENALTY_CAP, penalties.get(int(rid), 0.0) + PLAN_REFUSAL_PENALTY)
        for rid in {c["from"] for c in plan.get("changes", [])}:
            penalties[int(rid)] = min(CONTEXT_PENALTY_CAP, penalties.get(int(rid), 0.0) + (APPROVED_SWAP_PENALTY if plan.get("decision") == "approve" else SWAP_PENALTY))
        if plan.get("decision") == "approve":
            for rid in set(plan.get("suggested_recipe_ids", [])):
                penalties[int(rid)] = max(0.0, penalties.get(int(rid), 0.0) - APPROVAL_RECOVERY)
    return penalties
