"""Put a catalog recipe in the one shape the rest of the app expects. Runs once, on the recipe.

Recipes come from several sites, and not all of them save the same fields:

- Ingredients: some sites save the whole line as the name ("1 teaspoon cumin", quantity
  null). The amount is split off with the same parser the grocery list uses, so a recipe
  file says {"quantity": "1 teaspoon", "name": "cumin"}.
- Step ingredients: some sites list ingredients only once, above the steps, so every
  step's ingredients_for_step is empty. Each step then gets the ingredients it names, as
  "<quantity> <name>" lines, the same format Mealime recipes have.

normalize_recipe() changes nothing that is already in shape, so running it again is safe.
The catalog import runs it on every recipe, and scripts/normalize_catalog.py runs it on the
recipe files themselves so the files are normalized too.
"""

from __future__ import annotations

from app.domain.grocery import coerce_qty_name
import re

from app.domain.prep import SKIP_WORDS, _ingredient_heads, _words, mentioned


def _blank(value) -> bool:
    return not str(value or "").strip()


def normalize_ingredients(ingredients: list) -> tuple[list, int]:
    """Ingredients with any amount moved out of the name. Returns (ingredients, lines changed)."""
    out, changed = [], 0
    for ing in ingredients or []:
        if isinstance(ing, str):
            ing = {"quantity": None, "name": ing}
            changed += 1
        if not isinstance(ing, dict) or not _blank(ing.get("quantity")):
            out.append(ing)
            continue
        qty, name = coerce_qty_name("", ing.get("name") or "")
        if qty and name:
            ing = {**ing, "quantity": qty, "name": name}
            changed += 1
        out.append(ing)
    return out, changed


def _closest(text: str, hits: list[dict]) -> list[dict]:
    """When several ingredients match a step through the same word ("olive oil" and "pecan
    oil" both through "oil"), keep only the one whose name matches the step best."""
    said = set(_words(text))
    score = {id(i): len(said & set(_words(re.sub(r"\(.*?\)", "", i.get("name") or "")))) for i in hits}
    keep = []
    for ing in hits:
        heads = _ingredient_heads(ing.get("name") or "")[1] & said
        rivals = [o for o in hits if o is not ing and heads & set(_words(o.get("name") or ""))]
        if all(score[id(ing)] >= score[id(o)] for o in rivals):
            keep.append(ing)
    return keep


def ingredient_line(ing: dict) -> str:
    return " ".join(p for p in (str(ing.get("quantity") or "").strip(), str(ing.get("name") or "").strip()) if p)


def fill_step_ingredients(steps: list, ingredients: list) -> tuple[list, int]:
    """Steps with ingredients_for_step filled in from the ingredients each one names. Only
    for recipes where no step has any: a recipe that lists them on some steps (Mealime) leaves
    the rest empty on purpose, e.g. "Serve." Returns (steps, steps filled)."""
    dict_steps = [s for s in steps or [] if isinstance(s, dict)]
    if not dict_steps or any(not _blank(s.get("ingredients_for_step")) for s in dict_steps):
        return steps, 0
    ings = [i for i in ingredients or [] if isinstance(i, dict) and not _blank(i.get("name"))]
    out, filled, used = [], 0, set()
    for step in steps:
        if isinstance(step, dict):
            text = step.get("step") or step.get("text") or ""
            # "Wash your hands with soap and water" isn't the recipe's water. Each ingredient is
            # listed once, on the first step that uses it, so its amount isn't counted twice.
            hits = [] if SKIP_WORDS.search(text) else _closest(text, [i for i in mentioned(text, ings) if id(i) not in used])
            used.update(id(i) for i in hits)
            if hits:
                step = {**step, "ingredients_for_step": "\n".join(ingredient_line(i) for i in hits)}
                filled += 1
        out.append(step)
    return out, filled


def normalize_recipe(data: dict) -> tuple[dict, list[str]]:
    """The recipe in normalized shape, and a short note for each kind of change made."""
    notes = []
    ings, split = normalize_ingredients(data.get("ingredients") or [])
    if split:
        notes.append(f"split the amount off {split} ingredient(s)")
    steps, filled = fill_step_ingredients(data.get("instructions") or [], ings)
    if filled:
        notes.append(f"filled in ingredients on {filled} step(s)")
    if not notes:
        return data, []
    return {**data, "ingredients": ings, "instructions": steps}, notes


class RecipeNormalizer:
    """The one way a recipe is put in shape. Use RecipeNormalizer.normalize(recipe); the import,
    scripts/normalize_catalog.py and anything new should go through this class, so every recipe
    gets the same rules. The module functions above are its steps."""

    split_ingredients = staticmethod(normalize_ingredients)
    fill_step_ingredients = staticmethod(fill_step_ingredients)
    ingredient_line = staticmethod(ingredient_line)

    @staticmethod
    def normalize(data: dict) -> tuple[dict, list[str]]:
        """The recipe in normalized shape, and a short note for each kind of change made."""
        return normalize_recipe(data)
