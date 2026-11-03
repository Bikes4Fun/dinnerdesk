"""Explicitly import the configured private or fictional demo catalog into PostgreSQL."""

from __future__ import annotations

from app.assets import catalog_dir, food_dir
from app.domain.recipe_photos import is_uploaded_photo, our_photo_entries

import json
import os
from pathlib import Path

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
RETIRED_MARK = '%"retired": true%'


def public_recipe_sql(alias: str = "r") -> tuple[str, list]:
    """Household recipes always. Public catalog recipes only when the steps are
    ours, a photo path is set, and the recipe isn't retired. The photo is shown
    only if that file is tagged usable."""
    sql = (
        f"({alias}.household_id IS NOT NULL OR ("
        f"{alias}.provenance_json LIKE ?"
        f" AND {alias}.provenance_json NOT LIKE ?"
        f" AND COALESCE({alias}.photo_path, '') <> ''))"
    )
    return sql, [REWRITTEN_MARK, RETIRED_MARK]


def ready(data: dict, photos: dict[str, list[str]] | None = None) -> bool:
    """Only recipes with our own steps and a photo go into the database. With `photos`
    (from catalog_photos), the photo must also be one of ours on the allowlist."""
    if data.get("instructions_copied_from_third_party"):
        return False
    photo = (data.get("photo_path") or "").strip()
    if photos is None:
        return bool(photo)
    return Path(photo).name in photos.get("*", [])


UNREADY_SQL = (
    "household_id IS NULL AND (provenance_json NOT LIKE ? OR COALESCE(photo_path, '') = '')"
)


def remove_unready(conn) -> list:
    """Delete catalog rows that aren't ready. Rows a plan or a kitchen's copy still uses are
    kept and returned so they can be handled by hand."""
    used = (
        "(EXISTS (SELECT 1 FROM plan_slots s WHERE s.recipe_id = recipes.id)"
        " OR EXISTS (SELECT 1 FROM recipes c WHERE c.parent_recipe_id = recipes.id))"
    )
    conn.execute(f"DELETE FROM recipes WHERE {UNREADY_SQL} AND NOT {used}", (REWRITTEN_MARK,))
    return conn.execute(
        f"SELECT id, slug, name FROM recipes WHERE {UNREADY_SQL} ORDER BY id", (REWRITTEN_MARK,)
    ).fetchall()


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
            "instructions_rewritten_from": data.get("instructions_rewritten_from") or "",
            "instructions_copied_from_third_party": bool(
                data.get("instructions_copied_from_third_party")
            ),
            # Slug of the recipe this is a diet variant of. See app.domain.pool.
            "variant_of": str(data.get("variant_of") or ""),
            # Kept in the catalog files for reference, but no longer offered anywhere. Plans
            # and favorites that already point at it still open it.
            "retired": bool(data.get("retired")),
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
        """SELECT id, name, servings, cooking_minutes, instructions_json, cookware_json,
                  photo_path, provenance_json
           FROM recipes WHERE household_id IS NULL AND slug = ?""",
        (slug,),
    ).fetchone()
    if existing:
        rid = existing["id"]
        flags = json.loads(existing["provenance_json"] or "{}")
        keep_admin_tags = flags.get("admin_tags_edited") is True
        keep_primary = flags.get("admin_photo_edited") is True
        keep_content = flags.get("admin_content_edited") is True
        incoming_provenance = json.loads(provenance)
        if keep_admin_tags:
            incoming_provenance["admin_tags_edited"] = True
        if keep_primary:
            incoming_provenance["admin_photo_edited"] = True
        if keep_content:
            incoming_provenance["admin_content_edited"] = True
        provenance = json.dumps(incoming_provenance)
        photo = existing["photo_path"] if keep_primary or is_uploaded_photo(existing["photo_path"]) else incoming_photo
        if keep_content:
            name = existing["name"]
            servings = existing["servings"]
            minutes = existing["cooking_minutes"]
            steps_json = existing["instructions_json"]
            cookware = existing["cookware_json"] or "[]"
        else:
            servings = parse_servings(data.get("servings"))
            minutes = data.get("cooking_minutes")
            steps_json = json.dumps(steps)
        conn.execute(
            """UPDATE recipes SET name = ?, servings = ?, cooking_minutes = ?,
               instructions_json = ?, cookware_json = ?, source_url = ?,
               provenance_json = ?, photo_path = ?, updated_at = ?
               WHERE id = ? AND household_id IS NULL""",
            (
                name,
                servings,
                minutes,
                steps_json,
                cookware,
                data.get("source_url") or "",
                provenance,
                photo,
                ts,
                rid,
            ),
        )
        if not keep_content:
            _set_catalog_ingredients(conn, rid, ings, aliases)
        if not keep_admin_tags:
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


def rewritten_dir() -> Path | None:
    """dd_support's recipes/rewritten/ folder: DINNERDESK_REWRITTEN_DIR, or found next to the
    catalog (dd_support/catalog/dinnerdesk/data -> dd_support/recipes/rewritten)."""
    value = os.environ.get("DINNERDESK_REWRITTEN_DIR", "").strip()
    if value:
        path = Path(value).expanduser()
    else:
        parents = catalog_dir().resolve().parents
        if len(parents) < 3:
            return None
        path = parents[2] / "recipes" / "rewritten"
    return path if path.is_dir() else None


def catalog_photos() -> dict[str, list[str]]:
    """Our own photos that exist on disk, by archive recipe id, in allowlist order.
    Key "*" holds every usable file name."""
    listed = catalog_dir() / "recipe_photos.json"
    raw = json.loads(listed.read_text()) if listed.is_file() else {}
    folder = food_dir()
    out: dict[str, list[str]] = {"*": []}
    for name, recipe_id in our_photo_entries(raw):
        if not (folder / name).is_file():
            continue
        out["*"].append(name)
        if recipe_id is not None:
            out.setdefault(str(recipe_id), []).append(name)
    return out


def with_photo(data: dict, photos: dict[str, list[str]]) -> dict:
    """Keep the recipe's photo if it is one of ours; otherwise use our first photo for it."""
    current = (data.get("photo_path") or "").strip()
    if current and Path(current).name in photos["*"]:
        return data
    mine = photos.get(str(data.get("id") or ""), [])
    return {**data, "photo_path": f"food/{mine[0]}" if mine else ""}


def catalog_records() -> list[dict]:
    """Every catalog recipe: the catalog's recipes/*.json, plus dd_support rewrites for recipes the
    catalog lacks or still has third-party steps for. The catalog copy wins once it is rewritten,
    so edits made there are kept."""
    src = catalog_dir() / "recipes"
    if not src.is_dir() or not any(src.glob("*.json")):
        raise RuntimeError(f"No recipe JSON files in {src}; configure DINNERDESK_CATALOG_DIR explicitly")
    records: dict[str, dict] = {}
    for path in sorted(src.glob("*.json")):
        data = json.loads(path.read_text())
        if not (data.get("slug") or data.get("id")):
            data = {**data, "slug": path.stem}
        records[str(data.get("id") or data.get("slug"))] = data
    rewritten = rewritten_dir()
    for path in sorted(rewritten.glob("*.json")) if rewritten else []:
        data = json.loads(path.read_text())
        key = str(data.get("id") or path.stem.split("-", 1)[-1])
        current = records.get(key)
        if data.get("instructions_copied_from_third_party"):
            continue
        if current is None:
            records[key] = {**data, "slug": data.get("slug") or key}
        elif current.get("instructions_copied_from_third_party"):
            records[key] = {**current, **data, "slug": current.get("slug") or data.get("slug") or key}
    return list(records.values())


def import_recipes(conn, aliases: dict[str, str]) -> int:
    photos = catalog_photos()
    n = 0
    for data in catalog_records():
        data = with_photo(data, photos)
        if not ready(data, photos) and not conn.execute(
            "SELECT 1 FROM recipes WHERE household_id IS NULL AND slug = ?",
            (str(data.get("slug") or data.get("id")),),
        ).fetchone():
            continue
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
    for row in remove_unready(conn):
        print(f"kept unready recipe {row['id']} {row['slug']} ({row['name']}): still in use")
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
