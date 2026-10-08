"""Make-ahead prep, combined across every meal on the plan.

A recipe with steps tagged Prep uses only those (someone chose them), titled by the
step's heading. A recipe with no tags gets its likely make-ahead sentences picked out:
knife work, grating, sauces and marinades, but nothing that needs heat or happens at
serving time.

Tasks are grouped by what is being prepped, not by verb: "Peel and cube the potatoes" in
two recipes becomes one task, "Prep potatoes", with each meal's step as its own item.
A step with a heading ("Make the tzatziki: dice the cucumber…") becomes "Make tzatziki".
"""
from __future__ import annotations

import hashlib
import re
from app.domain.grocery import combine_quantities

# Anything with heat, assembly or serving belongs on cooking night, not prep day.
COOK_WORDS = re.compile(
    r"\b(heat|preheat|oven|bake[sd]?|baking|roast|broil|grill|sauté|saute|fry|fried|sear|simmer|boil|"
    r"cook|cooking|cooked|skillet|pan|pot|wok|microwave|toast|melt|warm|reheat|serve|serving|plate|"
    r"garnish|assemble|transfer|return|stir in|toss|top with|drizzle|sprinkle|spoon over|flip|"
    r"steam|poach|blend until hot|air fryer|slow cooker|instant pot)\b",
    re.I,
)
# Cut produce that browns or goes soggy is better done fresh.
FRESH_ONLY = re.compile(r"\b(avocado|apple|banana|pear)s?\b", re.I)
SKIP_WORDS = re.compile(r"\b(wash (your )?hands|gather|set out|read through|colander|drain)\b", re.I)

# What kind of make-ahead work a sentence is. First match wins.
KINDS = [
    ("marinate", re.compile(r"\b(marinate|marinade)\b", re.I)),
    ("sauce", re.compile(
        r"\b(sauce|dressing|vinaigrette|glaze|whisk|stir together|mix together|combine)\b", re.I)),
    ("grate", re.compile(r"\b(grate|shred)\b", re.I)),
    ("chop", re.compile(
        r"\b(chop|dice|mince|slice|peel|trim|julienne|cut|halve|quarter|zest|rinse|wash|"
        r"stem|core|seed|spiralize|strip the leaves|cube)\b", re.I)),
]
# Titles of the old verb groups, kept for likely_prep() callers and feedback categories.
KIND_TITLES = {
    "marinate": "Marinate proteins",
    "sauce": "Mix sauces & dressings",
    "grate": "Grate & shred cheese",
    "chop": "Chop vegetables & herbs",
}
VERB = {"marinate": "Marinate", "sauce": "Whisk", "grate": "Grate", "chop": "Prep"}

# Named sauces and components: "Make tzatziki", grouped across meals by name.
NAMED = re.compile(
    r"\b(tzatziki|pesto|salsa(?: verde)?|guacamole|pico de gallo|chimichurri|aioli|hummus|"
    r"teriyaki sauce|peanut sauce|tahini sauce|yogurt sauce|cilantro lime (?:ranch|rice)|ranch|"
    r"slaw|coleslaw|vinaigrette|gremolata|raita|relish|quick pickles?|pickled onions?)\b",
    re.I,
)

# Words that never name the thing being prepped.
FILLER = {
    "or", "and", "the", "with", "for", "of", "to", "into", "a", "an", "fresh", "ground", "small",
    "large", "medium", "dry", "dried", "red", "black", "white", "green", "yellow", "boneless",
    "skinless", "frozen", "pkg", "package", "can", "cans", "cup", "cups", "bunch", "crowns",
    "crown", "cloves", "clove", "pieces", "piece", "inch", "plain", "greek", "italian", "flat",
    "leaf", "baby", "lean", "extra", "virgin", "low", "sodium", "unsalted", "salted", "whole",
    "raw", "lb", "oz", "fl", "pint", "pints", "block", "head", "heads", "stalk", "stalks",
}
# A protein's first word is what recipes call it ("the chicken"), not "breasts".
PROTEINS = {"chicken", "beef", "pork", "turkey", "salmon", "shrimp", "steak", "lamb", "sausage",
            "tofu", "cod", "tilapia", "tuna"}

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n+")


def step_key(text: str) -> str:
    """Stable id for a step's wording, so feedback and check marks survive reordering."""
    norm = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha1(norm.encode()).hexdigest()[:12]


def _kind(text: str) -> str | None:
    if COOK_WORDS.search(text) or FRESH_ONLY.search(text) or SKIP_WORDS.search(text):
        return None
    for kind, pattern in KINDS:
        if pattern.search(text):
            if kind == "grate" and not re.search(r"\b(cheese|parmesan|mozzarella|cheddar|feta|"
                                                 r"carrot|zucchini|ginger|cabbage)\b", text, re.I):
                return "chop"
            return kind
    return None


def likely_prep(text: str) -> str | None:
    """The old verb-group title for a step that can be done ahead, or None."""
    kind = _kind(text)
    return KIND_TITLES[kind] if kind else None


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("oes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us")) and len(word) > 3:
        return word[:-1]
    return word


def _words(text: str) -> list[str]:
    return [_singular(w) for w in re.findall(r"[a-z]+", text.lower())]


def _ingredient_heads(name: str) -> tuple[str, set[str]]:
    """Display name and the words that identify an ingredient ("chicken or vegetable broth" → broth)."""
    main = name.split(",")[0]
    main = re.split(r"\bor\b", main)[-1]
    words = [w for w in _words(main) if w not in FILLER and len(w) > 2]
    if not words:
        return name, set()
    heads = {words[-1]}
    if words[0] in PROTEINS:
        heads.add(words[0])
    return main.strip(), heads


def mentioned(text: str, ingredients: list[dict]) -> list[dict]:
    """Ingredients this text actually names, in recipe order. Matches the item, not filler words."""
    found = set(_words(text))
    out = []
    for ing in ingredients:
        _, heads = _ingredient_heads(ing.get("name") or "")
        if heads and heads & found:
            out.append(ing)
    return out


PREP_VERB = re.compile(
    r"\b(?:chop|dice|mince|slice|peel|trim|cut|halve|quarter|grate|shred|zest|rinse|wash|"
    r"marinate|cube|core|seed)\b(?:,?\s+(?:and\s+)?(?:chop|dice|mince|slice|peel|cut|cube|rinse|wash))*",
    re.I)
OBJECT_END = re.compile(r"[,.;:]|\s(?:into|in|and|then|to|for|with|until|so)\s", re.I)
NOT_OBJECT = {"the", "a", "an", "all", "about", "of", "some", "half", "them", "it", "each",
              "cup", "cups", "tbsp", "tsp", "oz", "lb", "lbs", "clove", "cloves", "inch",
              "piece", "pieces", "finely", "roughly", "thinly", "large", "small"}


def _object_of(text: str) -> str | None:
    """Fallback when a recipe has no ingredient list: "Grate about 1 cup of mozzarella." → "mozzarella"."""
    # The last verb with something after it: "Wash, peel and large dice the potatoes".
    for m in reversed(list(PREP_VERB.finditer(text))):
        rest = " " + text[m.end():] + " "
        cut = OBJECT_END.search(rest)
        phrase = rest[: cut.start()] if cut else rest
        words = [w for w in re.findall(r"[a-z]+", phrase.lower()) if w not in NOT_OBJECT]
        if words:
            return " ".join(words[-3:])
    return None


def _heading(text: str) -> str | None:
    """'Make the tzatziki: dice…' → 'Make tzatziki'. Only short labels count as headings."""
    head = text.split("\n", 1)[0].strip().strip("#* ")
    label, sep, _ = head.partition(":")
    if not sep or not label.strip() or len(label) > 60:
        return None
    label = re.sub(r"\bthe\s+", "", label.strip(), flags=re.I)
    return label[:1].upper() + label[1:]


def _tagged_title(text: str) -> str:
    head = text.split('\n', 1)[0].strip().strip('#* ')
    if ':' in head:
        label, _, rest = head.partition(':')
        if not rest.strip() or len(label) < 60:
            head = label.strip()
    return (head.split('.')[0] or head)[:80]


def component_title(text: str, recipe_name: str) -> str | None:
    """Recognize explicit named components without inventing cooking instructions."""
    context = f"{recipe_name} {text}".casefold()
    if "mashed potato" in context and re.search(r"\b(potato|potatoes)\b", text, re.I):
        return "Prep mashed potatoes"
    if re.search(r"\b(tzatziki|tziki)\b", context) and re.search(r"\b(cucumber|yogurt|yoghurt|dill|garlic|tzatziki|tziki)\b", text, re.I):
        return "Make tzatziki"
    return None


def _sentences(text: str) -> list[str]:
    parts = [p.strip(" -•\t") for p in SENTENCE.split(text) if p and p.strip(" -•\t")]
    return parts or [text.strip()]


def _auto_items(text: str, ingredients: list[dict], meal_id, recipe_name: str = "") -> list[tuple[str, str, str]]:
    """(group key, title, sentence text) for each make-ahead sentence of an untagged step."""
    heading = _heading(text)
    body = text.split(":", 1)[1] if heading else text
    items: list[tuple[str, str, str]] = []
    for sentence in _sentences(body):
        kind = _kind(sentence)
        component = component_title(sentence, recipe_name)
        if component and not (COOK_WORDS.search(sentence) or FRESH_ONLY.search(sentence) or SKIP_WORDS.search(sentence)):
            items.append(("component:" + component.casefold(), component, sentence))
            continue
        if not kind:
            continue
        named = NAMED.search(sentence) or (NAMED.search(heading) if heading else None)
        if heading and (named or kind in ("sauce", "marinate")):
            title = heading if not named else f"Make {named.group(1).lower()}"
            key = "component:" + " ".join(_words(named.group(1) if named else heading))
        elif named:
            title = f"Make {named.group(1).lower()}"
            key = "component:" + " ".join(_words(named.group(1)))
        else:
            hits = mentioned(sentence, ingredients)
            generic = re.search(r"\b(sauce|dressing|vinaigrette|glaze|marinade)\b", sentence, re.I)
            if kind in ("sauce", "marinate") and generic:
                # An unnamed "dressing" is this meal's own; don't merge it with another meal's.
                word = generic.group(1).lower()
                items.append((f"component:{meal_id}:{word}", f"Make {word}", sentence))
                continue
            if hits:
                display, heads = _ingredient_heads(hits[0]["name"])
                thing = display.lower()
                key = f"{kind}:{sorted(heads)[0] if len(heads) == 1 else ' '.join(sorted(heads))}"
            else:
                thing = _object_of(sentence) or ""
                if not thing:
                    continue
                key = f"{kind}:{' '.join(_words(thing))}"
            title = f"{VERB[kind]} {thing}"
        items.append((key, title, sentence))
    return items


def prep_from_slots(slots: list[dict]) -> list[dict]:
    groups: dict[str, dict] = {}
    seen = set()
    for slot in slots:
        name = slot.get('recipe_name') or 'Meal'
        rid = slot.get('recipe_id')
        steps = slot.get('instructions') or []
        ingredients = slot.get('ingredients') or []
        texts = [(s.get('text') or s.get('step') or '').strip() for s in steps]
        tagged = any(s.get('prep') for s in steps)
        for i, (step, text) in enumerate(zip(steps, texts)):
            if not text or (rid, i) in seen:
                continue
            seen.add((rid, i))
            if tagged:
                if not step.get('prep'):
                    continue
                title = component_title(text, name) or _tagged_title(text)
                items = [(re.sub(r'\s+', ' ', title).casefold(), title, text)]
                auto = False
            else:
                items = _auto_items(text, ingredients, rid, name)
                auto = True
            for group, title, item_text in items:
                task = groups.setdefault(group, {
                    'title': title, 'notes': '', 'recipe_id': rid, 'auto': auto, 'recipe_ids': [],
                    'step_index': i, 'steps': [], 'meals': [], 'quantities': [], '_ingredients': {},
                    '_counted': set()})
                task['auto'] = task['auto'] and auto
                if rid not in task['recipe_ids']:
                    task['recipe_ids'].append(rid)
                task['steps'].append(f'{name}\n{item_text}')
                meal = next((m for m in task['meals'] if m['id'] == rid), None)
                if meal is None:
                    meal = {'id': rid, 'name': name, 'instructions': [], 'steps': []}
                    task['meals'].append(meal)
                if item_text in meal['instructions']:
                    continue
                meal['instructions'].append(item_text)
                meal['steps'].append({'key': step_key(item_text), 'text': item_text, 'auto': auto})
                for ing in mentioned(item_text, ingredients):
                    # Once per meal: two sentences about the same potatoes are still one amount.
                    if ing.get('quantity') and (rid, ing['name']) not in task['_counted']:
                        task['_counted'].add((rid, ing['name']))
                        task['_ingredients'].setdefault(ing['name'], []).append(ing['quantity'])
    for task in groups.values():
        task.pop('_counted')
        task['quantities'] = [f"{combine_quantities(amounts)} {name}"
                              for name, amounts in task.pop('_ingredients').items()]
        task['recipe_ids'].sort()
        task['notes'] = '\n\n'.join(task.pop('steps'))
    # Work shared by several meals first; otherwise keep recipe order.
    return sorted(groups.values(), key=lambda t: -len(t['meals']))
