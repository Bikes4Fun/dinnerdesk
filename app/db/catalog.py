"""Explicitly import the configured private or fictional demo catalog into PostgreSQL."""

from __future__ import annotations

from app.assets import catalog_dir

import json
import os

from app.db.database import ROOT, connect, init_db, now
from app.domain.ingredients import apply_alias, aisle_for, pantry_key, zone_for


def parse_servings(raw) -> int:
    if isinstance(raw, int) and raw > 0:
        return raw
    digits = ""
    for ch in str(raw or ""):
        if ch.isdigit():
            digits += ch
        elif digits:
            break
    if not digits or int(digits) <= 0:
        raise ValueError(f"Invalid recipe servings: {raw!r}")
    return int(digits)


REWRITTEN_MARK = '%"instructions_copied_from_third_party": false%'


def public_recipe_sql(alias: str = "r") -> tuple[str, list]:
    """Household recipes always. Public catalog recipes only when the steps are
    ours and a photo path is set. The photo is shown only if that file is tagged
    usable."""
    sql = (
        f"({alias}.household_id IS NOT NULL OR ("
        f"{alias}.provenance_json LIKE ?"
        f" AND COALESCE({alias}.photo_path, '') <> ''))"
    )
    return sql, [REWRITTEN_MARK]


SKIP_TAGS = {
    "allrecipes",
    "allstars",
    "chef_john",
    "myplate",
    "mealime",
    "instructions_copied_from_third_party",
    "instructions_reviewed",
    "incomplete",
    "customizable_template",
}


def load_aliases() -> dict[str, str]:
    path = catalog_dir() / "ingredients_review.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {pantry_key(k): pantry_key(v) for k, v in (data.get("aliases") or {}).items()}


def get_or_create_ingredient(conn, name: str, aliases: dict[str, str]) -> int:
    key = apply_alias(name, aliases)
    row = conn.execute(
        "SELECT id FROM ingredients WHERE canonical_name = ?", (key,)
    ).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO ingredients (canonical_name, aliases_json, aisle) VALUES (?, ?, ?)",
        (key, "[]", aisle_for(key)),
    )
    return int(cur.lastrowid)


def _steps_from_json(data: dict) -> list[dict]:
    steps = []
    for s in data.get("instructions") or []:
        if isinstance(s, str):
            steps.append({"text": s, "ings": "", "prep": False})
        else:
            steps.append(
                {
                    "text": s.get("step") or s.get("text") or "",
                    "ings": s.get("ingredients_for_step") or s.get("ings") or "",
                    "prep": bool(s.get("prep")),
                }
            )
    return steps


def _provenance_json(data: dict) -> str:
    return json.dumps(
        {
            "instructions_source": data.get("instructions_source") or "",
            "instructions_customized": bool(data.get("instructions_customized")) or (
                data.get("instructions_source") == "dinnerdesk"
                and data.get("instructions_copied_from_third_party") is False
            ),
            "instructions_rewritten_from": data.get("instructions_rewritten_from") or "",
            "instructions_copied_from_third_party": bool(
                data.get("instructions_copied_from_third_party")
            ),
        }
    )


def _set_catalog_ingredients(conn, recipe_id: int, ings: list, aliases: dict[str, str]) -> None:
    conn.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    for sort, ing in enumerate(ings):
        iname = ing.get("name") if isinstance(ing, dict) else str(ing)
        qty = ing.get("quantity") if isinstance(ing, dict) else ""
        iid = get_or_create_ingredient(conn, iname, aliases)
        conn.execute(
            """INSERT INTO recipe_ingredients
               (recipe_id, ingredient_id, quantity, unit, note, sort)
               VALUES (?, ?, ?, '', '', ?)""",
            (recipe_id, iid, qty or "", sort),
        )


def _set_catalog_tags(conn, recipe_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
    for tag in tags:
        conn.execute(
            "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?, ?)",
            (recipe_id, tag),
        )


def upsert_catalog_recipe(conn, data: dict, aliases: dict[str, str]) -> str:
    """Write a catalog row from JSON. Does not touch kitchen overlays."""
    slug = str(data.get("slug") or data.get("id") or "")
    if not slug:
        return "skip"
    name = data.get("name") or slug
    ings = data.get("ingredients") or []
    steps = _steps_from_json(data)
    tags = [t for t in (data.get("tags") or []) if t not in SKIP_TAGS]
    ts = now()
    incoming_photo = (data.get("photo_path") or "").strip()
    provenance = _provenance_json(data)
    cookware = json.dumps(data.get("cookware") or [])
    existing = conn.execute(
        "SELECT id, photo_path FROM recipes WHERE household_id IS NULL AND slug = ?",
        (slug,),
    ).fetchone()
    if existing:
        rid = existing["id"]
        photo = incoming_photo
        conn.execute(
            """UPDATE recipes SET name = ?, servings = ?, cooking_minutes = ?,
               instructions_json = ?, cookware_json = ?, source_url = ?,
               provenance_json = ?, photo_path = ?, updated_at = ?
               WHERE id = ? AND household_id IS NULL""",
            (
                name,
                parse_servings(data.get("servings")),
                data.get("cooking_minutes"),
                json.dumps(steps),
                cookware,
                data.get("source_url") or "",
                provenance,
                photo,
                ts,
                rid,
            ),
        )
        _set_catalog_ingredients(conn, rid, ings, aliases)
        _set_catalog_tags(conn, rid, tags)
        return "update"
    photo = incoming_photo
    cur = conn.execute(
        """INSERT INTO recipes (
            household_id, slug, name, servings, cooking_minutes,
            instructions_json, cookware_json, source_url, provenance_json,
            photo_path, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            None,
            slug,
            name,
            parse_servings(data.get("servings")),
            data.get("cooking_minutes"),
            json.dumps(steps),
            cookware,
            data.get("source_url") or "",
            provenance,
            photo,
            ts,
            ts,
        ),
    )
    rid = int(cur.lastrowid)
    _set_catalog_ingredients(conn, rid, ings, aliases)
    _set_catalog_tags(conn, rid, tags)
    return "insert"


def import_recipes(conn, aliases: dict[str, str]) -> int:
    src = catalog_dir() / "recipes"
    if not src.is_dir() or not any(src.glob("*.json")):
        raise RuntimeError(f"No recipe JSON files in {src}; configure DINNERDESK_CATALOG_DIR explicitly")
    n = 0
    for i, path in enumerate(sorted(src.glob("*.json"))):
        data = json.loads(path.read_text())
        if not (data.get("slug") or data.get("id")):
            data = {**data, "slug": path.stem}
        result = upsert_catalog_recipe(conn, data, aliases)
        if result == "insert":
            n += 1
    return n


def seed_household(conn) -> None:
    ts = now()
    conn.execute(
        "INSERT OR IGNORE INTO households (id, name, prefs_json, created_at) VALUES (1, ?, ?, ?)",
        ("Home kitchen", "{}", ts),
    )
    plan = conn.execute(
        "SELECT id FROM plans WHERE household_id = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    if not plan:
        conn.execute(
            "INSERT INTO plans (household_id, start_date, days, title, created_at) VALUES (1, date('now'), 7, ?, ?)",
            ("This week", ts),
        )


def should_import_catalog() -> bool:
    flag = (os.environ.get("DINNERDESK_IMPORT_CATALOG") or "").strip().lower()
    if flag in {"0", "false", "no"}:
        return False
    if flag in {"1", "true", "yes"}:
        return True
    return False


def load_catalog(conn) -> int:
    seed_household(conn)
    n = import_recipes(conn, load_aliases())
    conn.commit()
    return n


def main() -> None:

    conn = connect()
    try:
        init_db(conn)
        conn.commit()
    finally:
        conn.close()
    conn = connect()
    try:
        n = load_catalog(conn)
        total = conn.execute("SELECT COUNT(*) AS c FROM recipes").fetchone()["c"]
        print(f"imported {n} new recipes; catalog now {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
