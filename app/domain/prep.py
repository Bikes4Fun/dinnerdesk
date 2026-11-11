"""Make-ahead prep, combined across every meal on the plan.

A recipe with steps tagged Prep uses only those (someone chose them), titled by the
step's heading. A recipe with no tags gets its likely make-ahead sentences picked out:
knife work, grating and cold sauces. Reviewed exceptions include roasting beets and
cooking quinoa; meat work and salad assembly stay on cooking day.

Tasks are grouped by what is being prepped, not by verb: "Peel and cube the potatoes" in
two recipes becomes one task, "Prep potatoes", with each meal's step as its own item.
A step with a heading ("Make the tzatziki: dice the cucumber…") becomes "Make tzatziki".
"""
from __future__ import annotations

import hashlib
import re
from fractions import Fraction

from app.domain.grocery import combine_quantities, parse_qty, scale_quantity

# Default filter; _cooking_component supplies narrowly reviewed heat exceptions.
COOK_WORDS = re.compile(
    r"\b(heat|preheat|oven|bake[sd]?|baking|roast|broil|grill|sauté|saute|fry|fried|sear|simmer|boil|"
    r"cook|cooking|cooked|skillet|pan|pot|wok|microwave|toast|melt|warm|reheat|serve|serving|plate|"
    r"garnish|assemble|transfer|return|stir in|toss|top with|drizzle|sprinkle|spoon over|flip|"
    r"steam|poach|blend until hot|air fryer|slow cooker|instant pot|saucepan|sauce pan|stovetop|stove|"
    r"thicken|thickens|thickened|bring to a|bring it to a|reduce by|reduce until|caramelize|"
    r"medium heat|low heat|high heat)\b",
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
        r"stem|core|seed|spiralize|strip|cube)\b", re.I)),
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
    "root",  # "ginger root" is ginger; "trim the roots" must not match it
}
# A protein's first word is what recipes call it ("the chicken"), not "breasts".
PROTEINS = {"chicken", "beef", "pork", "turkey", "salmon", "shrimp", "steak", "lamb", "sausage",
            "tofu", "cod", "tilapia", "tuna"}
MEAT = PROTEINS - {"tofu"}
MEAT_WORDS = re.compile(r"\b(?:" + "|".join(sorted(MEAT | {"fish", "bacon", "ham", "meat"})) + r")\b", re.I)

# A head word that names two different groceries, told apart by the word before it:
# "black pepper" (seasoning) vs "bell pepper" (vegetable). A seasoning one only matches when
# the text says it in full, so "dice the pepper" means the bell pepper (#29).
SEASONING_QUALIFIERS = {"pepper": {"black", "white", "cayenne", "ground"},
                         "powder": {"curry", "garlic", "onion", "chili", "chilli"}}

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n+")

# Bottled sauces are groceries, not something being made: "mix the turkey with the soy sauce".
BOTTLED = re.compile(r"\b(?:soy|fish|hot|worcestershire|chili-garlic|sriracha|hoisin|oyster|teriyaki|"
                     r"barbecue|bbq|tomato|pizza|marinara|enchilada|pasta|alfredo|buffalo|steak|sweet chili)"
                     r"\s+sauce\b", re.I)

GREEN_ONION = re.compile(r"\b(?:green|spring) onions?\b|\bscallions?\b", re.I)

PREP_VERB = re.compile(
    r"\b(?:chop|dice|mince|slice|peel|trim|cut|halve|quarter|grate|shred|zest|rinse|wash|"
    r"marinate|cube|core|seed)\b(?:,?\s+(?:and\s+)?(?:chop|dice|mince|slice|peel|cut|cube|rinse|wash))*",
    re.I)
# Where the thing being prepped ends: "grate the cheese | on the large holes of a box grater".
OBJECT_END = re.compile(
    r"[,.;:]|\s(?:into|in|and|then|to|for|with|until|so|on|onto|using|over|through|at|by|if)\s", re.I)
NOT_OBJECT = {"the", "a", "an", "all", "about", "of", "some", "half", "them", "it", "each",
              "cup", "cups", "tbsp", "tsp", "oz", "lb", "lbs", "clove", "cloves", "inch",
              "piece", "pieces", "finely", "roughly", "thinly", "large", "small",
              "off", "up", "away", "out", "down", "any", "your"}
# "Trim the roots off the scallions", "seeds from the peppers": the part named first is not
# the grocery; the thing after of/from/off is.
PART_OF = re.compile(
    r"\b(?:roots?|ends?|stems?|tops?|leaves|skins?|peels?|seeds?|ribs?|cores?|pits?|rinds?|fat)\s+"
    r"(?:of|from|off)\s+(.+)$", re.I)

# Sections of the Weekend prep screen (#21), in screen order. Grouped by what the food is,
# so one ingredient is one row no matter how many meals use it.
SECTIONS = [
    ("veg", "Vegetables"),
    ("herbs", "Aromatics, herbs & citrus"),
    ("protein", "Protein"),
    ("cheese", "Cheese & dairy"),
    ("sauce", "Sauces & dressings"),
    ("other", "More prep"),
]
# Aromatics, herbs and citrus share one section, aromatics first: the onion and garlic you
# chop for the base of a dish, then the herbs, then the citrus.
AROMATIC_BASE = {"onion", "garlic", "ginger", "shallot", "scallion", "leek", "jalapeno", "jalapeño",
                 "chili", "chile", "lemongrass"}
HERBS = {"chive", "parsley", "cilantro", "basil", "dill", "mint", "thyme", "rosemary", "oregano",
         "sage", "tarragon", "herb"}
CITRUS = {"lemon", "lime", "orange", "zest"}
AROMATICS = AROMATIC_BASE | HERBS | CITRUS
MORE_PROTEINS = PROTEINS | {"chickpea", "bean", "lentil", "egg", "tempeh", "fish", "thigh",
                            "breast", "cutlet", "chop", "fillet", "meatball", "ham", "bacon"}
CHEESES = {"cheese", "parmesan", "mozzarella", "cheddar", "feta", "ricotta", "yogurt", "yoghurt",
           "cream", "butter", "milk"}
VERB_WORDS = ("Prep ", "Grate ", "Whisk ", "Marinate ")

# What the steps actually say to do, for the item's name: "Peel and mince garlic" (not "Prep
# garlic"). A modifier is kept with its verb: "Finely dice onion".
CUT_VERB = re.compile(
    r"\b(?:(finely|thinly|roughly|coarsely|thickly)\s+)?"
    r"(wash|rinse|scrub|peel|trim|core|seed|stem|halve|quarter|chop|dice|mince|slice|julienne|cube|"
    r"cut|break|grate|shred|zest|spiralize|crush|smash|tear|strip)\b", re.I)
# A new clause starts at a comma, "then", or "and" + another cut: "Break the cauliflower into
# florets | and cut the tomatoes", so the tomatoes' cut doesn't land on the cauliflower.
CLAUSE = re.compile(
    r"[,;]|\s+then\s+|\s+and\s+(?=(?:(?:finely|thinly|roughly|coarsely|thickly)\s+)?"
    r"(?:wash|rinse|scrub|peel|trim|core|seed|stem|halve|quarter|chop|dice|mince|slice|julienne|"
    r"cube|cut|break|grate|shred|zest|pull|remove|strip)\b)", re.I)
PART_WORDS = {"base", "individual", "root", "end", "stem", "top", "leave", "leaf", "skin", "peel", "seed", "rib", "core",
              "pit", "rind", "fat", "them", "it", "both", "everything", "all", "half", "piece"}
# Words that describe the cut or a side step, not another grocery: "cut it into bite-size
# florets", "pull off the leaves". A clause with only these stays on the item.
SHAPE_WORDS = {"floret", "bite", "size", "sized", "dice", "slice", "cube", "chunk", "strip", "wedge",
               "round", "ring", "matchstick", "inch", "thin", "thick", "pull", "remove", "discard",
               "separate", "aside", "reserve", "keep", "away", "rough", "fine", "even",
               # Where it goes next isn't another grocery: "dice it and add it to the bowl".
               "add", "bowl", "dish", "plate", "board", "set", "later", "serving", "pat", "towel",
               "paper", "stir", "put", "place",
               # Which way it's cut: "quarter it the long way", "slice it crosswise".
               "long", "way", "lengthwise", "crosswise", "across", "halves", "wise",
               # The tool, not the food: "grate it on the large holes of a box grater".
               "hole", "box", "grater", "peeler", "processor", "food", "knife", "spoon",
               # Shapes named as nouns: "slice it into half-moons", "coins", "noodles".
               "split", "half", "moon", "coin", "noodle", "shred", "ribbon", "fry", "fries", "spear", "stick"}

WASH_VERBS = ("wash", "rinse", "scrub")
TRIM_VERBS = ("peel", "trim", "core", "seed", "stem")
SAME_CUT = {"cube": "dice"}

class SemanticPrepEngine:
    """Shared prep system for every client: select, contextualize, group and store.

    Generation state is local to each build, so one engine can safely serve multiple
    households. Override policy methods when introducing another reviewed strategy;
    clients continue to consume the same task/step contract.
    """

    def _prep_subject(self, text: str) -> str:
        # A destination is not another ingredient being cut.
        return re.split(r"\b(?:set|reserve|keep)\b.*?\b(?:aside|for)\b", text, maxsplit=1, flags=re.I)[0]


    def _excluded(self, text: str) -> bool:
        # A packaged stock is a sauce/grain ingredient, not active meat preparation.
        meat_context = re.sub(r"\b(?:chicken|beef|fish|turkey|pork)\s+(?:broth|stock)\b", '', text, flags=re.I)
        return bool(MEAT_WORDS.search(meat_context) or re.search(
            r"\b(?:salad|romaine|lettuce|greens|arugula|spinach)\b.*\b(?:dressing|mix|toss)\b|"
            r"\b(?:dressing)\b.*\b(?:salad|romaine|lettuce|greens|arugula|spinach)\b|"
            r"\b(?:halfway|baste|basting)\b", text, re.I))


    def step_key(self, text: str) -> str:
        """Stable id for a step's wording, so feedback and check marks survive reordering."""
        norm = re.sub(r"\s+", " ", text).strip().casefold()
        return hashlib.sha1(norm.encode()).hexdigest()[:12]


    def _kind(self, text: str, force: bool = False) -> str | None:
        """What kind of make-ahead work this is. `force` (a step someone said was missing from
        prep) skips the cooking/serving filters and calls plain knife work "chop"."""
        skip = SKIP_WORDS.search(text) and not re.search(r"\bdrain the tofu\b.*\b(?:cut|cube)\b", text, re.I)
        if not force and (self._excluded(text) or COOK_WORDS.search(text) or FRESH_ONLY.search(text) or skip):
            return None
        plain = BOTTLED.sub("", text)
        for kind, pattern in KINDS:
            if pattern.search(plain):
                if kind == "grate" and not re.search(r"\b(cheese|parmesan|mozzarella|cheddar|feta|"
                                                     r"carrot|zucchini|ginger|cabbage)\b", text, re.I):
                    return "chop"
                return kind
        return None


    def step_sentences(self, text: str) -> list[str]:
        """The pieces of a recipe step that prep can list one at a time (a heading is dropped)."""
        heading = self._heading(text)
        return self._sentences(text.split(":", 1)[1] if heading else text)


    def likely_prep(self, text: str) -> str | None:
        """The old verb-group title for a step that can be done ahead, or None."""
        kind = self._kind(text)
        return KIND_TITLES[kind] if kind else None


    def _singular(self, word: str) -> str:
        if word.endswith("ies") and len(word) > 4:
            return word[:-3] + "y"
        if word.endswith(("oes", "ches", "shes")):
            return word[:-2]
        if word.endswith("s") and not word.endswith(("ss", "us")) and len(word) > 3:
            return word[:-1]
        return word


    def _words(self, text: str) -> list[str]:
        # Green onions are their own grocery, not the onion: "scallion" keeps them apart.
        return [self._singular(w) for w in re.findall(r"[a-z]+", GREEN_ONION.sub("scallion", text).lower())]


    def _ingredient_heads(self, name: str) -> tuple[str, set[str]]:
        """Display name and the words that identify an ingredient ("chicken or vegetable broth" → broth)."""
        main = name.split(",")[0]
        main = re.split(r"\bor\b", main)[-1]
        words = [w for w in self._words(main) if w not in FILLER and len(w) > 2]
        if not words:
            return name, set()
        heads = {words[-1]}
        if words[0] in PROTEINS:
            heads.add(words[0])
        return main.strip(), heads


    def _qualifier(self, words: list[str], head: str) -> str | None:
        """The word right before `head` ("black" in "ground black pepper")."""
        if head in words:
            i = words.index(head)
            return words[i - 1] if i > 0 else None
        return None


    def mentioned(self, text: str, ingredients: list[dict]) -> list[dict]:
        """Ingredients this text actually names, in recipe order. Matches the item, not filler words."""
        # "salt and pepper" is the seasoning, never the bell pepper.
        text = re.sub(r"\bsalt\s*(?:,|and|&)\s*pepper\b", "salt and black pepper", text, flags=re.I)
        text = re.sub(r"\bmayo\b", "mayonnaise", text, flags=re.I)
        text_words = self._words(text)
        found = set(text_words)
        out = []
        for ing in ingredients:
            name = ing.get("name") or ""
            _, heads = self._ingredient_heads(name)
            hit = heads & found
            if not hit:
                continue
            for head in list(hit):
                seasoning = SEASONING_QUALIFIERS.get(head)
                if not seasoning:
                    continue
                mine = self._qualifier(self._words(name.split(",")[0]), head)
                said = self._qualifier(text_words, head)
                if mine in seasoning:
                    ok = said == mine  # "black pepper" only when the text says "black pepper"
                else:
                    ok = said not in seasoning  # "bell pepper" unless the text says "black pepper"
                if not ok:
                    hit.discard(head)
            if hit:
                out.append(ing)
        return out


    def _object_of(self, text: str) -> str | None:
        """Fallback when a recipe has no ingredient list: "Grate about 1 cup of mozzarella." → "mozzarella"."""
        # The last verb with something after it: "Wash, peel and large dice the potatoes".
        for m in reversed(list(PREP_VERB.finditer(text))):
            rest = " " + text[m.end():] + " "
            part = PART_OF.search(rest)
            if part:
                rest = " " + part.group(1) + " "
            cut = OBJECT_END.search(rest)
            phrase = rest[: cut.start()] if cut else rest
            words = [w for w in re.findall(r"[a-z]+", phrase.lower()) if w not in NOT_OBJECT]
            if words:
                return " ".join(words[-3:])
        return None


    def _heading(self, text: str) -> str | None:
        """'Make the tzatziki: dice…' → 'Make tzatziki'. Only short labels count as headings."""
        head = text.split("\n", 1)[0].strip().strip("#* ")
        label, sep, _ = head.partition(":")
        if not sep or not label.strip() or len(label) > 60:
            return None
        label = re.sub(r"\bthe\s+", "", label.strip(), flags=re.I)
        return label[:1].upper() + label[1:]


    def _tagged_title(self, text: str) -> str:
        head = text.split('\n', 1)[0].strip().strip('#* ')
        if ':' in head:
            label, _, rest = head.partition(':')
            if not rest.strip() or len(label) < 60:
                head = label.strip()
        return (head.split('.')[0] or head)[:80]


    def component_title(self, text: str, recipe_name: str) -> str | None:
        """Recognize explicit named components without inventing cooking instructions."""
        context = f"{recipe_name} {text}".casefold()
        if "mashed potato" in context and re.search(r"\b(potato|potatoes)\b", text, re.I):
            return "Prep mashed potatoes"
        if re.search(r"\b(tzatziki|tziki)\b", context) and re.search(r"\b(cucumber|yogurt|yoghurt|dill|garlic|tzatziki|tziki)\b", text, re.I):
            return "Make tzatziki"
        return None


    def _sentences(self, text: str) -> list[str]:
        parts = [p.strip(" -•\t") for p in SENTENCE.split(text) if p and p.strip(" -•\t")]
        return parts or [text.strip()]


    def _names(self, hits: list[dict]) -> str:
        shown = [self._ingredient_heads(h["name"])[0].lower() for h in hits[:3]]
        return shown[0] if len(shown) == 1 else ", ".join(shown[:-1]) + " & " + shown[-1]


    def _auto_items(self,
        text: str, ingredients: list[dict], meal_id, recipe_name: str = "", force: bool = False
    ) -> list[tuple[str, str, str, list[str] | None]]:
        """(group key, title, sentence text, ingredient names it covers) for each make-ahead sentence
        of an untagged step. Names None means every ingredient the sentence mentions. `force`: the
        person said this sentence belongs in prep, so it is always listed."""
        heading = self._heading(text)
        body = text.split(":", 1)[1] if heading else text
        items: list[tuple[str, str, str]] = []
        for sentence in self._sentences(body):
            kind = self._kind(sentence, force)
            component = self.component_title(sentence, recipe_name)
            if component and (force or not (COOK_WORDS.search(sentence) or FRESH_ONLY.search(sentence) or SKIP_WORDS.search(sentence))):
                items.append(("component:" + component.casefold(), component, sentence, None))
                continue
            if not kind:
                continue
            named = NAMED.search(sentence) or (NAMED.search(heading) if heading else None)
            if heading and (named or kind in ("sauce", "marinate")):
                title = heading if not named else f"Make {named.group(1).lower()}"
                key = "component:" + " ".join(self._words(named.group(1) if named else heading))
                items.append((key, title, sentence, None))
                continue
            elif named:
                title = f"Make {named.group(1).lower()}"
                key = "component:" + " ".join(self._words(named.group(1)))
            else:
                hits = self.mentioned(self._prep_subject(sentence), ingredients)
                generic = re.search(r"\b(sauce|dressing|vinaigrette|glaze|marinade)\b", BOTTLED.sub('', sentence), re.I)
                if kind in ("sauce", "marinate") and generic:
                    # An unnamed "dressing" is this meal's own; don't merge it with another meal's.
                    word = generic.group(1).lower()
                    items.append((f"component:{meal_id}:{word}", f"Make {word}", sentence, None))
                    continue
                if kind == "sauce" and len(hits) != 1 or kind == "sauce" and not self._whiskable(hits[0]):
                    # "Whisk the oil, vinegar and garlic" is this meal's own mix, not "Whisk garlic".
                    title = f"Mix {self._names(hits)}" if len(hits) > 1 else "Make sauce"
                    items.append((f"component:{meal_id}:mix:{self.step_key(sentence)}", title, sentence, None))
                    continue
                if kind in ("chop", "grate") and len(hits) > 1:
                    # "Dice the onion, pepper and celery": each ingredient is its own task, with only
                    # its own amount, so one sentence doesn't pile every amount onto the first item.
                    for hit in hits:
                        display, heads = self._ingredient_heads(hit["name"])
                        key = f"{kind}:{' '.join(sorted(heads))}"
                        items.append((key, f"{VERB[kind]} {display.lower()}", sentence, [hit["name"]]))
                    continue
                if hits:
                    display, heads = self._ingredient_heads(hits[0]["name"])
                    thing = display.lower()
                    key = f"{kind}:{sorted(heads)[0] if len(heads) == 1 else ' '.join(sorted(heads))}"
                else:
                    thing = self._object_of(sentence) or ""
                    if not thing:
                        continue
                    key = f"{kind}:{' '.join(self._words(thing))}"
                title = f"{VERB[kind]} {thing}"
            items.append((key, title, sentence, None))
        if force and not items:
            # Nothing to name it by ("Soak the beans overnight"): list the sentence as its own item.
            title = re.split(r"[,;.]", body.strip(), maxsplit=1)[0].strip()[:60] or "Prep step"
            items.append((f"added:{meal_id}:{self.step_key(body)}", title, body.strip(), None))
        return items


    def _whiskable(self, ing: dict) -> bool:
        """Something you'd whisk on its own (eggs, cream, yogurt), not an aromatic like garlic."""
        _, heads = self._ingredient_heads(ing.get("name") or "")
        return bool(heads & {"egg", "cream", "yogurt", "milk", "buttermilk", "mayonnaise", "mayo"})


    def _section(self, kind: str, title: str, quantities: list[str]) -> str:
        if kind in ("sauce", "mix") or NAMED.search(title) or re.search(
                r"\b(sauce|dressing|vinaigrette|glaze|marinade|mix)\b", title, re.I):
            return "sauce"
        if kind == "marinate":
            return "protein"
        words = set(self._words(title + " " + " ".join(quantities)))
        protein = words & MORE_PROTEINS
        if {"green", "string", "wax", "snap"} & words:
            protein -= {"bean"}  # green beans are a vegetable
        if protein:
            return "protein"
        if kind == "grate" and words & CHEESES or words & (CHEESES - {"cream", "butter", "milk"}):
            return "cheese"
        if words & AROMATICS:
            return "herbs"
        if kind in ("chop", "grate", "component"):
            return "veg"
        return "other"


    def _herb_rank(self, task: dict) -> int:
        """Order inside "Aromatics, herbs & citrus": aromatics, then herbs, then citrus."""
        if task["section"] != "herbs":
            return 0
        words = set(self._words(task["item"]))
        return 0 if words & AROMATIC_BASE else 1 if words & HERBS else 2


    def _item(self, title: str) -> tuple[str, str]:
        """("Onion", "") for "Prep onion"; ("Mozzarella", "Grate") for "Grate mozzarella"."""
        for verb in VERB_WORDS:
            if title.startswith(verb):
                rest = title[len(verb):].strip()
                return rest[:1].upper() + rest[1:], "" if verb == "Prep " else verb.strip()
        return title, ""


    def _verbs_for(self, text: str, item_words: set[str]) -> list[str]:
        """The cut verbs in `text` that apply to the item, in order.
        "Rinse the green onions, trim off the roots, and chop them" → rinse, trim, chop.
        "Wash, peel and dice the potatoes" → wash, peel, dice. "Dice the onion, mince the garlic"
        → mince, for garlic."""
        out: list[str] = []
        pending: list[str] = []  # verbs waiting for their object: "Wash, | peel and dice the potatoes"
        on_item = False
        last: list[str] = []
        for clause in CLAUSE.split(text):
            words = self._words(clause)
            verbs = []
            said: set[str] = set()  # the verbs as written, so "cut … into dice" doesn't make "cut" an object
            for m in CUT_VERB.finditer(clause):
                before = self._words(clause[: m.start()])[-3:]
                if "into" in before or (before and before[-1] in {"a", "an", "the", "of", "one"}):
                    continue  # "cut into small dice", "a quarter of": nouns, not steps
                verb = m.group(2).lower()
                said.add(self._singular(verb))
                if verb == "cut" and re.match(r"\s+(?:away|off)\b", clause[m.end():], re.I):
                    verb = "trim"  # "cut off the roots"
                elif verb == "cut" and re.match(r"[^,;.]*?\binto\s+(?:[\w-]+\s+){0,2}(?:dice|cubes?)\b",
                                                clause[m.end():], re.I):
                    verb = "dice"  # "cut the tomatoes into medium dice"
                verbs.append(f"{m.group(1).lower()} {verb}" if m.group(1) else verb)
            verb_words = {self._singular(v.split()[-1]) for v in verbs} | said
            objects = [w for w in words if w not in verb_words and w not in NOT_OBJECT
                       and w not in PART_WORDS and w not in FILLER and w not in SHAPE_WORDS and len(w) > 2
                       and w not in {"finely", "thinly", "roughly", "coarsely", "thickly"}]
            if item_words & set(words):
                on_item = True
                verbs = pending + (verbs or ([] if pending else last))  # "Dice the onion, pepper and celery"
                pending = []
            elif objects:
                on_item = False  # this clause is about something else
                pending = []
            elif verbs and not on_item:
                pending += verbs
            if on_item:
                out += [v for v in verbs if v not in out]
            if verbs:
                last = verbs
        return out[-3:]


    def _phrase(self, verbs: list[str]) -> str:
        text = verbs[0] if len(verbs) == 1 else ", ".join(verbs[:-1]) + " and " + verbs[-1]
        return text[:1].upper() + text[1:]


    def _merge_verbs(self, per_step: list[list[str]]) -> list[str]:
        """One verb list for every meal's steps: wash, then peel/trim, then ONE cut.
        Curry "rinse" + "break into florets", salmon "rinse … cut into florets" → rinse, chop.
        Cuts that differ become "chop" (each meal's own cut is listed under the item)."""
        wash: dict[str, int] = {}
        trims: set[str] = set()
        cuts: list[str] = []
        for verbs in per_step:
            for verb in verbs:
                base = verb.split()[-1]
                if base in WASH_VERBS:
                    wash[verb] = wash.get(verb, 0) + 1
                elif base in TRIM_VERBS:
                    trims.add(base)
                elif verb not in cuts:
                    cuts.append(verb)
        out = [max(wash, key=wash.get)] if wash else []  # ties keep the first meal's
        order = [v for v in TRIM_VERBS if v in trims]
        if "peel" in order and "trim" in order:
            order.remove("trim")  # trimming the ends is part of peeling an onion
        out += order
        bases = {SAME_CUT.get(c.split()[-1], c.split()[-1]) for c in cuts}
        if len(cuts) == 1:
            out.append(cuts[0])
        elif len(bases) == 1:
            out.append(bases.pop())  # "finely dice" and "dice" → "dice"
        elif bases and bases <= {"slice", "julienne"}:
            out.append("slice")
        elif bases and bases <= {"grate", "shred", "zest"}:
            out.append("grate")
        elif bases:
            out.append("chop")
        return out


    def _action(self, task: dict) -> str:
        """What the meals say to do to this item, merged across meals, or "" when they don't say."""
        words = {w for w in self._words(task["item"]) if w not in FILLER and len(w) > 2}
        per_step = [self._verbs_for(self._prep_subject(text), words) for meal in task["meals"] for text in meal["instructions"]]
        verbs = self._merge_verbs([v for v in per_step if v])
        return self._phrase(verbs) if verbs else ""


    def _cooking_component(self, text: str) -> tuple[str, str] | None:
        """Narrow heat exceptions from reviewed feedback, never general cooking."""
        if self._excluded(text) or FRESH_ONLY.search(text):
            return None
        if re.search(r"\broast\b", text, re.I) and re.search(r"\bbeets?\b", text, re.I):
            return "beets", "Roast beets"
        if re.search(r"\bquinoa\b", text, re.I) and re.search(r"\b(?:boil|cook|simmer)\b", text, re.I):
            return "quinoa", "Cook quinoa"
        return None


    def _display_context(self, texts: list[str], ingredients: list[dict]) -> dict[str, tuple[str, list[str]]]:
        """Enrich presentation without changing the wording used by feedback/checkmarks.

        Only resolve 'other half' when a preceding explicit split has one clear subject.
        Unknown divisions remain labelled as recipe totals rather than invented amounts.
        """
        result = {}
        split = None
        for text in texts:
            for sentence in self.step_sentences(text):
                hits = self.mentioned(self._prep_subject(sentence), ingredients)
                display = sentence
                divided = bool(re.search(r"\b(?:half|quarter|third|divided|remaining|rest)\b", sentence, re.I))
                half = re.search(r"\b(?:the )?other half\b", sentence, re.I)
                if half and split:
                    display = sentence[:half.start()] + f"half of the {split['name']}" + sentence[half.end():]
                    hits = [split] + [h for h in hits if h != split]
                amounts = []
                for ing in hits:
                    quantity = ing.get('quantity')
                    if not quantity:
                        continue
                    if half and split == ing and parse_qty(quantity):
                        amount = scale_quantity(quantity, Fraction(1, 2))
                        amounts.append(f"{amount} {ing['name']} (half)")
                    elif half and split == ing:
                        amounts.append(f"Half of {quantity} {ing['name']} (recipe total)")
                    else:
                        amounts.append(f"{quantity} {ing['name']}" + (" (recipe total; divided)" if divided and not half else ""))
                result[sentence] = (display, amounts)
                if re.search(r"\b(?:set|reserve)\b.*\bhalf\b.*\baside\b", sentence, re.I):
                    split = hits[0] if len(hits) == 1 else None
                elif half:
                    split = None
        return result


    def _storage(self, task: dict, kind: str) -> str:
        # Cooked food: foodsafety.gov/keep-food-safe/4-steps-to-food-safety.
        # No invented shelf-life for arbitrary raw mixtures or cut produce.
        if kind == 'cook':
            return ('Refrigerate promptly in shallow covered containers at 40°F (4°C) or below, '
                    'within 2 hours (1 hour above 90°F/32°C). Use within 3–4 days or freeze.')
        if task['section'] == 'sauce':
            return 'Refrigerate in a covered container. Keep separate from salad vegetables until serving; follow the shortest ingredient storage limit.'
        if task['section'] in ('veg', 'herbs'):
            return 'Refrigerate in a covered container; keep washed greens and herbs dry and separate from dressing until serving.'
        return ''


    def build(self, slots: list[dict]) -> list[dict]:
        groups: dict[str, dict] = {}
        seen = set()
        for slot in slots:
            name = slot.get('recipe_name') or 'Meal'
            rid = slot.get('recipe_id')
            steps = slot.get('instructions') or []
            ingredients = slot.get('ingredients') or []
            texts = [(s.get('text') or s.get('step') or '').strip() for s in steps]
            context = self._display_context(texts, ingredients)
            cooking = None
            tagged = any(s.get('prep') for s in steps)
            # Steps the household said were missing from prep (#21) come after the recipe's own,
            # listed even when the picker skipped them. Each is one sentence, matched by wording.
            work = [(i, step, text, False) for i, (step, text) in enumerate(zip(steps, texts))]
            work += [(None, {}, a.strip(), True) for a in slot.get('added') or [] if a and a.strip()]
            for i, step, text, forced in work:
                if not text or (rid, i) in seen:
                    continue
                if forced:
                    listed = any(text in m['instructions'] for task in groups.values()
                                 for m in task['meals'] if m['id'] == rid)
                    if listed:
                        continue  # already in prep
                    items = self._auto_items(text, ingredients, rid, name, force=True)
                    auto = False
                elif tagged:
                    seen.add((rid, i))
                    if not step.get('prep'):
                        continue
                    title = self.component_title(text, name) or self._tagged_title(text)
                    items = [(re.sub(r'\s+', ' ', title).casefold(), title, text, None)]
                    auto = False
                else:
                    seen.add((rid, i))
                    items = self._auto_items(text, ingredients, rid, name)
                    # Keep the complete contiguous quinoa cooking sequence, including
                    # pronoun-only simmer/cover directions. New ingredients end it.
                    for sentence in self.step_sentences(text):
                        target = self._cooking_component(sentence)
                        continuation = (cooking and cooking[0] == 'quinoa'
                                        and not self._excluded(sentence)
                                        and re.search(r"\b(?:simmer|cover|reduce|absorb|fluff|stand)\b", sentence, re.I)
                                        and all(re.search(r"\b(?:quinoa|broth|water|salt)\b", h['name'], re.I)
                                                for h in self.mentioned(sentence, ingredients)))
                        if target or continuation:
                            cooking = target or cooking
                            items.append((f'cook:{rid}:{cooking[0]}', cooking[1], sentence, None))
                        else:
                            cooking = None
                    auto = True
                for group, title, item_text, only in items:
                    task = groups.setdefault(group, {
                        'title': title, 'notes': '', 'recipe_id': rid, 'auto': auto, 'recipe_ids': [],
                        '_kind': ('mix' if ':mix:' in group else group.split(':', 1)[0]) if auto else 'tagged',
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
                    display, amounts = context.get(item_text, (item_text, []))
                    if only is not None:
                        amounts = [a for a in amounts if any(n in a for n in only)]
                    meal['steps'].append({'key': self.step_key(item_text), 'text': item_text, 'auto': auto,
                                          'display_text': display, 'quantities': amounts,
                                          **({'added': True} if forced else {})})
                    for ing in self.mentioned(self._prep_subject(display), ingredients):
                        if only is not None and ing['name'] not in only:
                            continue
                        # Once per meal: two sentences about the same potatoes are still one amount.
                        if ing.get('quantity') and (rid, ing['name']) not in task['_counted']:
                            task['_counted'].add((rid, ing['name']))
                            quantity = ing['quantity']
                            if f"half of the {ing['name']}" in display and parse_qty(quantity):
                                quantity = scale_quantity(quantity, Fraction(1, 2))
                            task['_ingredients'].setdefault(ing['name'], []).append(quantity)
        for task in groups.values():
            task.pop('_counted')
            task['quantities'] = [f"{combine_quantities(amounts)} {name}"
                                  for name, amounts in task.pop('_ingredients').items()]
            task['recipe_ids'].sort()
            task['notes'] = '\n\n'.join(task.pop('steps'))
            kind = task.pop('_kind')
            task['section'] = self._section(kind, task['title'], task['quantities'])
            task['item'], task['action'] = self._item(task['title'])
            task['storage'] = self._storage(task, kind)
            if task['auto'] and kind in ('chop', 'grate'):  # not "Prep mashed potatoes" or sauces
                action = self._action(task)
                if action:
                    task['action'] = action
                    task['title'] = f"{action} {task['item'][:1].lower()}{task['item'][1:]}"
        # Work shared by several meals first; otherwise keep recipe order.
        return sorted(groups.values(), key=lambda t: (self._herb_rank(t), -len(t['meals'])))


# Stable entry points for feedback identities and existing domain callers.
def step_key(text: str) -> str:
    return SemanticPrepEngine().step_key(text)


def step_sentences(text: str) -> list[str]:
    return SemanticPrepEngine().step_sentences(text)


def likely_prep(text: str) -> str | None:
    return SemanticPrepEngine().likely_prep(text)


def mentioned(text: str, ingredients: list[dict]) -> list[dict]:
    return SemanticPrepEngine().mentioned(text, ingredients)


def component_title(text: str, recipe_name: str) -> str | None:
    return SemanticPrepEngine().component_title(text, recipe_name)


def prep_from_slots(slots: list[dict]) -> list[dict]:
    return SemanticPrepEngine().build(slots)


# Recipe normalization shares the same ingredient vocabulary.
def _ingredient_heads(name: str) -> tuple[str, set[str]]:
    return SemanticPrepEngine()._ingredient_heads(name)


def _words(text: str) -> list[str]:
    return SemanticPrepEngine()._words(text)
