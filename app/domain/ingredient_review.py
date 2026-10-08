"""Read-only ingredient proposals plus separately stored human answers."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import tempfile
from collections import defaultdict
from functools import lru_cache
from pathlib import Path


SOURCES = (
    ("allrecipes", "allrecipes_bulk_scrape"),
    ("mealime", "mealime_bulk_scrape"),
    ("myplate", "myplate_bulk_scrape"),
)
LEADING_AMOUNT = re.compile(
    r"^(?:about\s+)?(?:\d+(?:\s+\d+/\d+|[./-]\d+)*|[¼½¾⅓⅔⅛⅜⅝⅞])\s*",
    re.I,
)
LEADING_UNIT = re.compile(
    r"^(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lbs?|ounces?|oz|"
    r"cloves?|cans?|packages?|pkgs?|slices?|pieces?|pinches?|heads?|"
    r"bunch(?:es)?|stalks?|sprigs?)\s+(?:of\s+)?",
    re.I,
)
TRAILING_WEIGHT = re.compile(
    r"\s*\((?:about\s+)?[\d\s./-]+\s*(?:pounds?|lbs?|ounces?|oz|grams?|g)\)\s*$",
    re.I,
)
LEADING_PACKAGE_WEIGHT = re.compile(
    r"^\([\d\s./-]+\s*(?:pounds?|lbs?|ounces?|oz|grams?|g|ml|fl oz)\)\s*",
    re.I,
)
BROAD_MODIFIERS = re.compile(
    r"\b(large|small|medium|baby|frozen|dried|bone-in|boneless|skinless|"
    r"whole|low-fat|fat-free)\b",
    re.I,
)
NON_FOOD = re.compile(
    r"\b(aluminum foil|parchment paper|wax paper|plastic wrap|paper towels?|"
    r"toothpicks?|wooden skewers?|kitchen twine)\b",
    re.I,
)
PLAIN_WATER = re.compile(
    r"^(?:(?:boiling|hot|warm|cold|ice|tap)\s+)?water(?:\s*\([^)]*\))?$",
    re.I,
)
DESCRIPTOR_ONLY = re.compile(
    r"^(?:boneless|skinless|bone-in|large|small|medium)$",
    re.I,
)


def _clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip(" ,.")


def ingredient_core(raw: str, quantity_is_separate: bool) -> str:
    """Extract a comparable food name while retaining the original as evidence."""
    value = _clean_space(raw)
    value = LEADING_PACKAGE_WEIGHT.sub("", value)
    if not quantity_is_separate:
        value = LEADING_AMOUNT.sub("", value)
        value = LEADING_PACKAGE_WEIGHT.sub("", value)
        value = LEADING_UNIT.sub("", value)
        value = LEADING_PACKAGE_WEIGHT.sub("", value)
        value = re.sub(
            r"\b(boneless|skinless)\s*,\s*(boneless|skinless)\b",
            r"\1 \2",
            value,
            flags=re.I,
        )
        value = re.sub(r"^(large|small|medium)\s*,\s*", r"\1 ", value, flags=re.I)
        value = re.sub(r"^(?:large|small|medium)\s+", "", value, flags=re.I)
        value = TRAILING_WEIGHT.sub("", value)
        value = value.split(",", 1)[0]
    return _clean_space(value).lower()


def _singular_word(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return f"{word[:-3]}y"
    if word.endswith("oes") and len(word) > 3:
        return word[:-2]
    if word.endswith(("ches", "shes", "xes", "zes")) and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def plural_key(name: str) -> str:
    words = name.split()
    if words:
        words[-1] = _singular_word(words[-1])
    return " ".join(words)


def proposal_key(name: str) -> str:
    value = re.sub(r"\s*\([^)]*\)\s*", " ", name)
    value = re.sub(r"^fresh\s+", "", value)
    return plural_key(_clean_space(value).lower())


def broad_key(name: str) -> str:
    value = BROAD_MODIFIERS.sub(" ", proposal_key(name))
    return _clean_space(value)


FLAG_RULES = (
    (("cheese", "fat-free cheese"), "Generic cheese needs a specific type."),
    (
        ("vegetables", "(10 ounces each) frozen vegetables"),
        "Generic vegetables need a specific grocery form.",
    ),
    (
        ("red pepper", "fresh red pepper"),
        "Ambiguous red pepper: bell pepper vs spice.",
    ),
    (("black beans",), "Unspecified black beans: canned vs dry."),
    (("bell pepper",), "Unspecified bell pepper needs a color."),
    (("corn",), "Unspecified corn: fresh, cob, frozen, or canned."),
    (("ginger",), "Unspecified ginger: fresh vs ground."),
    (
        ("protein pasta", "protein pasta (uncooked)"),
        "Protein pasta may not be the intended product.",
    ),
    (("dill",), "Unspecified dill: fresh vs dried."),
    (("milk",), "Unspecified milk type. Default later is 2%."),
    (("chicken",), "Unspecified chicken cut."),
    (("skinless boneless chicken",), "Unspecified skinless boneless chicken cut."),
    (("pork chops",), "Unspecified pork chops: bone-in vs boneless."),
    (("turkey",), "Unspecified turkey cut."),
    (
        ("(4 oz each) salmon fillets (skin-on)",),
        "Confirm quantity logging for 4 oz skin-on salmon fillets.",
    ),
    (
        ("(14.5 ounces) tomatoes",),
        "Unspecified tomatoes: confirm canned type and size.",
    ),
)


def _source_data(root: Path) -> Path:
    from app.assets import ROOT, catalog_dir
    return catalog_dir() if root.resolve() == ROOT else root / "data"


def answers_path(root: Path) -> Path:
    return _source_data(root) / "ingredient_normalization_answers.json"


def flagged_recipes_path(root: Path) -> Path:
    return _source_data(root) / "recipes_needing_manual_review.json"


def _read_json(path: Path, default):
    return json.loads(path.read_text())


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def load_answers(root: Path) -> dict:
    return _read_json(
        answers_path(root),
        {
            "notes": "Review answers only. Does not modify recipes or PostgreSQL.",
            "answers": {},
            "audits": {},
        },
    )


def save_answers(root: Path, data: dict) -> None:
    _write_json(answers_path(root), data)


def collect_flagged_recipes(root: Path) -> list[dict]:
    wanted = {name: reason for names, reason in FLAG_RULES for name in names}
    rows = []
    seen = set()
    for source, path in _recipe_files(root):
        recipe = _read_json(path, {})
        recipe_name = _clean_space(str(recipe.get("name") or path.stem))
        source_url = str(recipe.get("source_url") or "")
        for ingredient in recipe.get("ingredients") or []:
            if isinstance(ingredient, dict):
                raw = str(ingredient.get("name") or "")
                separate = ingredient.get("quantity") is not None
            else:
                raw = str(ingredient)
                separate = False
            core = ingredient_core(raw, separate)
            reason = wanted.get(core)
            if not reason:
                continue
            key = (source_url or recipe_name, core, _clean_space(raw))
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "name": recipe_name,
                    "source": source,
                    "source_url": source_url,
                    "raw": _clean_space(raw),
                    "ingredient_name": core,
                    "reason": reason,
                }
            )
    return sorted(
        rows,
        key=lambda row: (row["reason"], row["source"], row["name"], row["raw"]),
    )


def save_flagged_recipes(root: Path, rows: list[dict]) -> None:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["reason"]].append(row)
    _write_json(
        flagged_recipes_path(root),
        {
            "notes": (
                "Recipes to edit by hand so ingredient text matches grocery "
                "normalization. Does not modify recipe files until you do."
            ),
            "count": len(rows),
            "reasons": [
                {"reason": reason, "count": len(items), "recipes": items}
                for reason, items in grouped.items()
            ],
        },
    )


def _recipe_files(root: Path):
    for source, directory in SOURCES:
        source_root = _source_data(root) / directory
        for path in sorted(source_root.glob("**/recipes/*.json")):
            yield source, path


@lru_cache(maxsize=4)
def build_proposals(root_value: str) -> list[dict]:
    root = Path(root_value)
    forms: dict[str, dict] = {}
    for source, path in _recipe_files(root):
        recipe = _read_json(path, {})
        recipe_name = _clean_space(str(recipe.get("name") or path.stem))
        source_url = str(recipe.get("source_url") or "")
        for ingredient in recipe.get("ingredients") or []:
            if isinstance(ingredient, dict):
                raw = str(ingredient.get("name") or "")
                separate = ingredient.get("quantity") is not None
            else:
                raw = str(ingredient)
                separate = False
            core = ingredient_core(raw, separate)
            if (
                not core
                or NON_FOOD.search(core)
                or PLAIN_WATER.match(core)
                or DESCRIPTOR_ONLY.match(core)
            ):
                continue
            row = forms.setdefault(
                core,
                {"text": core, "count": 0, "sources": defaultdict(int), "recipes": {}},
            )
            row["count"] += 1
            row["sources"][source] += 1
            recipe_key = f"{source}:{path.relative_to(root)}"
            row["recipes"][recipe_key] = {
                "name": recipe_name,
                "source": source,
                "source_url": source_url,
                "raw": _clean_space(raw),
                "ingredient_name": core,
            }

    by_key: dict[str, list[dict]] = defaultdict(list)
    for row in forms.values():
        by_key[broad_key(row["text"])].append(row)

    proposals = []
    for key, rows in by_key.items():
        plural_forms = {plural_key(row["text"]) for row in rows}
        if len(rows) < 2 or len(plural_forms) == 1:
            continue
        names = []
        recipe_examples = {}
        for row in rows:
            names.append(
                {
                    "text": row["text"],
                    "count": row["count"],
                    "sources": dict(row["sources"]),
                    "recipes": list(row["recipes"].values())[:20],
                }
            )
            recipe_examples.update(row["recipes"])
        digest = hashlib.sha1(key.encode()).hexdigest()[:12]
        proposal_keys = {proposal_key(row["text"]) for row in rows}
        proposals.append(
            {
                "id": f"group-{digest}",
                "suggested_name": max(rows, key=lambda row: row["count"])["text"],
                "queue": "easy" if len(proposal_keys) == 1 else "harder",
                "names": sorted(names, key=lambda row: (-row["count"], row["text"])),
                "recipe_hits": sum(row["count"] for row in rows),
                "recipes": list(recipe_examples.values())[:20],
            }
        )
    return sorted(
        proposals,
        key=lambda row: (
            row["queue"] != "easy",
            -row["recipe_hits"],
            row["suggested_name"],
        ),
    )


def review_groups(root: Path) -> list[dict]:
    data = load_answers(root)
    answers = data.get("answers") or {}
    audits = data.get("audits") or {}
    groups = [
        {
            **group,
            "answer": answers.get(group["id"]) or {},
            "audit": audits.get(group["id"]) or {},
        }
        for group in build_proposals(str(root))
    ]
    current_ids = {group["id"] for group in groups}
    for group_id, answer in answers.items():
        snapshot = answer.get("proposal_snapshot") or {}
        names = snapshot.get("names") or []
        if (
            group_id in current_ids
            or answer.get("status") != "answered"
            or not names
            or all(
                NON_FOOD.search(str(row.get("text") or ""))
                or PLAIN_WATER.match(str(row.get("text") or ""))
                or DESCRIPTOR_ONLY.match(str(row.get("text") or ""))
                for row in names
            )
        ):
            continue
        recipes = {}
        for row in names:
            for recipe in row.get("recipes") or []:
                key = (
                    recipe.get("source"),
                    recipe.get("source_url"),
                    recipe.get("name"),
                )
                recipes[key] = recipe
        groups.append(
            {
                "id": group_id,
                "suggested_name": snapshot.get("suggested_name")
                or max(names, key=lambda row: row.get("count", 0))["text"],
                "queue": "historical",
                "names": names,
                "recipe_hits": snapshot.get("recipe_hits", 0),
                "recipes": list(recipes.values())[:20],
                "answer": answer,
                "audit": audits.get(group_id)
                or {
                    "verdict": "question",
                    "reason": (
                        "This answer came from an earlier parser grouping. "
                        "Confirm the revised breakdown before applying anything."
                    ),
                    "review_status": "pending",
                    "historical": True,
                },
                "historical": True,
            }
        )

    expanded = list(groups)
    pending = list(groups)
    known_ids = {group["id"] for group in groups}
    while pending:
        parent = pending.pop(0)
        answer = parent.get("answer") or {}
        if answer.get("status") != "answered" or answer.get("action") == "separate":
            continue
        selected = set(answer.get("names") or [])
        remaining = [
            row for row in parent["names"] if row.get("text") not in selected
        ]
        if len(remaining) < 2:
            continue
        remainder_key = "\n".join(sorted(row["text"] for row in remaining))
        digest = hashlib.sha1(remainder_key.encode()).hexdigest()[:10]
        group_id = f"{parent['id']}-remaining-{digest}"
        if group_id in known_ids:
            continue
        recipes = {}
        for row in remaining:
            for recipe in row.get("recipes") or []:
                key = (
                    recipe.get("source"),
                    recipe.get("source_url"),
                    recipe.get("name"),
                )
                recipes[key] = recipe
        follow_up = {
            "id": group_id,
            "suggested_name": max(
                remaining, key=lambda row: row.get("count", 0)
            )["text"],
            "queue": "harder",
            "names": remaining,
            "recipe_hits": sum(row.get("count", 0) for row in remaining),
            "recipes": list(recipes.values())[:20],
            "answer": answers.get(group_id) or {},
            "audit": audits.get(group_id) or {},
            "follow_up": True,
            "parent_id": parent["id"],
        }
        expanded.append(follow_up)
        pending.append(follow_up)
        known_ids.add(group_id)

    recipes_by_name: dict[str, list[dict]] = {}
    for group in expanded:
        for row in group.get("names") or []:
            text = row.get("text")
            examples = row.get("recipes") or []
            if text and examples and text not in recipes_by_name:
                recipes_by_name[text] = examples
    for group in expanded:
        for row in group.get("names") or []:
            if row.get("recipes"):
                continue
            extras = recipes_by_name.get(row.get("text") or "")
            if extras:
                row["recipes"] = extras
        if not group.get("recipes"):
            examples = []
            for row in group.get("names") or []:
                examples.extend(row.get("recipes") or [])
            group["recipes"] = examples[:20]
    return expanded


def save_group_notes(root: Path, group_id: str, notes: str) -> None:
    data = load_answers(root)
    answer = data.setdefault("answers", {}).setdefault(group_id, {})
    answer["notes"] = notes
    save_answers(root, data)


def save_group_answer(
    root: Path,
    group_id: str,
    action: str,
    target: str,
    selected_names: list[str],
) -> None:
    group = next((row for row in review_groups(root) if row["id"] == group_id), None)
    if group is None:
        raise KeyError(group_id)
    allowed = {row["text"] for row in group["names"]}
    if any(name not in allowed for name in selected_names):
        raise ValueError("A selected name is not in this group")
    if action != "separate" and not selected_names:
        raise ValueError("Select at least one name")
    target = _clean_space(target)
    if not target:
        raise ValueError("Choose a name")
    data = load_answers(root)
    old = data.setdefault("answers", {}).get(group_id) or {}
    data["answers"][group_id] = {
        **old,
        "status": "answered",
        "action": action,
        "target": target,
        "names": selected_names,
        "proposal_snapshot": {
            "suggested_name": group["suggested_name"],
            "names": group["names"],
            "recipe_hits": group["recipe_hits"],
        },
    }
    save_answers(root, data)


def save_group_audit(
    root: Path,
    group_id: str,
    verdict: str,
    reason: str,
    suggested_action: str | None,
    suggested_target: str,
    suggested_names: list[str],
) -> None:
    group = next((row for row in review_groups(root) if row["id"] == group_id), None)
    if group is None or group["answer"].get("status") != "answered":
        raise KeyError(group_id)
    allowed = {row["text"] for row in group["names"]}
    if any(name not in allowed for name in suggested_names):
        raise ValueError("A suggested name is not in this group")
    if suggested_action and suggested_action != "separate" and not suggested_names:
        raise ValueError("Select at least one suggested name")
    suggested_target = _clean_space(suggested_target)
    if suggested_action and not suggested_target:
        raise ValueError("Choose a suggested target")

    data = load_answers(root)
    old = data.setdefault("audits", {}).get(group_id) or {}
    answer = data.get("answers", {}).get(group_id) or {}
    data["audits"][group_id] = {
        **old,
        "verdict": verdict,
        "reason": _clean_space(reason),
        "suggested_action": suggested_action,
        "suggested_target": suggested_target,
        "suggested_names": suggested_names,
        "review_status": old.get("review_status", "pending"),
        "original_answer": old.get("original_answer")
        or {
            "action": answer.get("action"),
            "target": answer.get("target"),
            "names": answer.get("names") or [],
            "notes": answer.get("notes") or "",
        },
    }
    save_answers(root, data)


def resolve_group_audit(root: Path, group_id: str, resolution: str) -> None:
    data = load_answers(root)
    audit = data.setdefault("audits", {}).get(group_id)
    if not audit:
        answer = data.get("answers", {}).get(group_id) or {}
        if answer.get("status") != "answered":
            raise KeyError(group_id)
        audit = {
            "verdict": "question",
            "reason": (
                "This answer came from an earlier parser grouping. "
                "Confirm the revised breakdown before applying anything."
            ),
            "original_answer": {
                "action": answer.get("action"),
                "target": answer.get("target"),
                "names": answer.get("names") or [],
                "notes": answer.get("notes") or "",
            },
        }
        data["audits"][group_id] = audit
    audit["review_status"] = "re_review" if resolution == "re_review" else "resolved"
    audit["resolution"] = resolution
    current = data.get("answers", {}).get(group_id) or {}
    audit["resolved_answer"] = {
        "action": current.get("action"),
        "target": current.get("target"),
        "names": current.get("names") or [],
        "notes": current.get("notes") or "",
    }
    save_answers(root, data)
