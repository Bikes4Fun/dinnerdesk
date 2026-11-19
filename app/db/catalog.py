"""Explicitly import the configured private or fictional demo catalog into PostgreSQL."""

from __future__ import annotations

from app.domain.recipe_normalize import RecipeNormalizer
from app.assets import catalog_dir, food_dir
from app.domain.catalog_sync import RECIPE_WORKFLOW_FIELDS, content_differences, same_photo, steps_from_db, tags_match
from app.domain.recipe_photos import (
    archive_id_of, catalog_gallery, found_ai_photos, is_uploaded_photo, our_photo_entries,
)

import json
import os
from pathlib import Path

from app.db.database import ROOT, connect, init_db, now
from app.domain.ingredients import apply_alias, aisle_for, pantry_key, zone_for
from app.domain.coming_soon import ComingSoon
from app.domain.offering import Offering
from app.domain.pantry_catalog import ingredient_name


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
# A recipe that has one of our photos but whose steps aren't in our own words yet. It's stored
# without steps and stays out of every list but Recipes, where it shows greyed out as coming soon.
COMING_SOON_MARK = ComingSoon.MARK_SQL


def public_recipe_sql(alias: str = "r") -> tuple[str, list]:
    """Household recipes always. Public catalog recipes only when the steps are
    ours, a photo path is set, and the recipe isn't retired, pizza, breakfast, or a
    snack. The photo is shown only if that file is tagged usable."""
    withheld_name = " AND ".join(f"{alias}.name NOT ILIKE ?" for _ in Offering.LIKE)
    exact = ", ".join("?" for _ in Offering.EXACT)
    sql = (
        f"({alias}.household_id IS NOT NULL OR ("
        f"{alias}.provenance_json LIKE ?"
        f" AND {alias}.provenance_json NOT LIKE ?"
        f" AND COALESCE({alias}.photo_path, '') <> ''"
        f" AND {withheld_name}"
        f" AND LOWER(BTRIM({alias}.name)) NOT IN ({exact})))"
    )
    return sql, [REWRITTEN_MARK, RETIRED_MARK, *Offering.LIKE, *Offering.EXACT]


def ready(data: dict, photos: dict[str, list[str]] | None = None) -> bool:
    """Only recipes with our own steps and a photo go into the database. With `photos`
    (from catalog_photos), the photo must also be one of ours on the allowlist.
    Pizza, breakfast, and snacks are never ready."""
    if Offering.withheld(str(data.get("name") or ""), data.get("tags")):
        return False
    if data.get("instructions_copied_from_third_party"):
        return False
    photo = (data.get("photo_path") or "").strip()
    if photos is None:
        return bool(photo)
    return Path(photo).name in photos.get("*", [])


UNREADY_SQL = (
    "household_id IS NULL AND (provenance_json NOT LIKE ? OR COALESCE(photo_path, '') = '')"
    " AND NOT (provenance_json LIKE ? AND COALESCE(photo_path, '') <> '')"
)


def remove_unready(conn) -> list:
    """Delete catalog rows that aren't ready. Rows a plan or a kitchen's copy still uses are
    kept and returned so they can be handled by hand."""
    used = (
        "(EXISTS (SELECT 1 FROM plan_slots s WHERE s.recipe_id = recipes.id)"
        " OR EXISTS (SELECT 1 FROM recipes c WHERE c.parent_recipe_id = recipes.id))"
    )
    marks = (REWRITTEN_MARK, COMING_SOON_MARK)
    conn.execute(f"DELETE FROM recipes WHERE {UNREADY_SQL} AND NOT {used}", marks)
    return conn.execute(
        f"SELECT id, slug, name FROM recipes WHERE {UNREADY_SQL} ORDER BY id", marks
    ).fetchall()


def remove_withheld(conn) -> list:
    """Delete catalog pizza, breakfast, and snacks. Rows a plan or a kitchen's copy still
    uses are kept and returned. The catalog files are not touched."""
    used = (
        "(EXISTS (SELECT 1 FROM plan_slots s WHERE s.recipe_id = ?)"
        " OR EXISTS (SELECT 1 FROM recipes c WHERE c.parent_recipe_id = ?))"
    )
    kept = []
    for row in conn.execute(
        "SELECT id, slug, name FROM recipes WHERE household_id IS NULL ORDER BY id"
    ):
        if not Offering.withheld(row["name"]):
            continue
        if conn.execute(f"SELECT 1 WHERE {used}", (row["id"], row["id"])).fetchone():
            kept.append(row)
            continue
        conn.execute("DELETE FROM recipes WHERE id = ?", (row["id"],))
    return kept


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
    key = ingredient_name(apply_alias(name, aliases))
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
            "reviewed": data.get("reviewed") is True,
            **{field: data.get(field) is True for field in RECIPE_WORKFLOW_FIELDS},
            "coming_soon": bool(data.get("coming_soon")),
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


def _db_content(conn, row) -> dict:
    """The parts of a catalog row an admin can edit, in the recipe file's format."""
    flags = json.loads(row["provenance_json"] or "{}")
    ingredients = flags.get("admin_ingredients")
    if ingredients is None:
        ingredients = [
            {"name": r["canonical_name"], "quantity": r["quantity"]}
            for r in conn.execute(
                """SELECT i.canonical_name, ri.quantity FROM recipe_ingredients ri
                   JOIN ingredients i ON i.id = ri.ingredient_id
                   WHERE ri.recipe_id = ? ORDER BY ri.sort""",
                (row["id"],),
            )
        ]
    return {
        "name": row["name"],
        "servings": row["servings"],
        "cooking_minutes": row["cooking_minutes"],
        "instructions": steps_from_db(row["instructions_json"]),
        "cookware": json.loads(row["cookware_json"] or "[]"),
        "ingredients": ingredients,
    }


def _db_tags(conn, recipe_id: int) -> list[str]:
    return [r["tag"] for r in conn.execute(
        "SELECT tag FROM recipe_tags WHERE recipe_id = ? ORDER BY tag", (recipe_id,))]


def upsert_catalog_recipe(conn, data: dict, aliases: dict[str, str], report: dict | None = None) -> str:
    """Write a catalog row from JSON. Does not touch kitchen overlays.

    A part an admin edited in the app (content, tags or primary photo) is kept over the file.
    When the file already says the same thing, the admin flag is cleared so later file edits
    apply again; when it says something different, the admin's version stays and the recipe
    is listed in report["conflicts"]."""
    report = report if report is not None else {}
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
        keep_retired = flags.get("admin_retired_edited") is True
        keep_reviewed = flags.get("admin_reviewed_edited") is True

        def settle(part: str, keep: bool, find_differences) -> bool:
            if not keep:
                return False
            differences = find_differences()
            if not differences:
                report.setdefault("in_sync", []).append({"slug": slug, "part": part})
                return False  # the file has caught up: clear the flag
            report.setdefault("conflicts", []).append(
                {"slug": slug, "name": existing["name"], "part": part, "fields": differences})
            return True

        keep_content = settle("content", keep_content, lambda: content_differences(data, _db_content(conn, existing)))
        keep_admin_tags = settle(
            "tags", keep_admin_tags,
            lambda: [] if tags_match(data.get("tags"), _db_tags(conn, rid), SKIP_TAGS) else ["tags"])
        keep_primary = settle(
            "photo", keep_primary,
            lambda: [] if same_photo(incoming_photo, existing["photo_path"]) else ["photo_path"])
        keep_retired = settle(
            "retired", keep_retired,
            lambda: [] if bool(data.get("retired")) == (flags.get("retired") is True) else ["retired"])
        incoming_provenance = json.loads(provenance)
        for field in RECIPE_WORKFLOW_FIELDS:
            keep = settle(
                field, flags.get(f"admin_{field}_edited") is True,
                lambda field=field: [] if (data.get(field) is True) == (flags.get(field) is True) else [field])
            if keep:
                incoming_provenance[field] = flags.get(field) is True
                incoming_provenance[f"admin_{field}_edited"] = True
        keep_reviewed = settle(
            "reviewed", keep_reviewed,
            lambda: [] if (data.get("reviewed") is True) == (flags.get("reviewed") is True) else ["reviewed"])
        if keep_reviewed:
            incoming_provenance["reviewed"] = flags.get("reviewed") is True
            incoming_provenance["admin_reviewed_edited"] = True
        if keep_retired:  # removed from (or brought back to) the app in the admin screen
            incoming_provenance["retired"] = flags.get("retired") is True
            incoming_provenance["admin_retired_edited"] = True
        if keep_admin_tags:
            incoming_provenance["admin_tags_edited"] = True
        if keep_primary:
            incoming_provenance["admin_photo_edited"] = True
        if keep_content:
            incoming_provenance["admin_content_edited"] = True
            if "admin_ingredients" in flags:
                incoming_provenance["admin_ingredients"] = flags["admin_ingredients"]
        # Photos an admin deleted stay deleted while recipe_photos.json still lists them. Once
        # the sync has taken them off the list, there's nothing left to hide.
        listed = set(catalog_gallery(archive_id_of(data.get("source_url"), slug)))
        removed = [p for p in flags.get("removed_photos") or [] if p in listed]
        if removed:
            incoming_provenance["removed_photos"] = removed
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


# Kept as names here so existing callers and tests read the same; the rules are in ComingSoon.
coming_soon_record = ComingSoon.record
is_coming_soon = ComingSoon.is_candidate


def catalog_photos() -> dict[str, list[str]]:
    """Our own photos that exist on disk, by archive recipe id: listed ones in allowlist order,
    then unlisted AI photos found in the folder (see recipe_photos.found_ai_photos).
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
    # Our AI photos in the folder count without being listed; a _PRIMARY_ one goes first.
    for name, recipe_id in found_ai_photos(folder):
        if name in out["*"]:
            continue
        out["*"].append(name)
        if recipe_id is not None:
            mine = out.setdefault(str(recipe_id), [])
            mine.insert(0, name) if "_PRIMARY_" in name else mine.append(name)
    return out


def with_photo(data: dict, photos: dict[str, list[str]]) -> dict:
    """Keep the recipe's photo if it is one of ours; otherwise use our first photo for it."""
    current = (data.get("photo_path") or "").strip()
    if current and Path(current).name in photos["*"]:
        return data
    mine = photos.get(str(data.get("id") or ""), [])
    return {**data, "photo_path": f"food/{mine[0]}" if mine else ""}


def catalog_records() -> list[dict]:
    """Every catalog recipe: catalog/dinnerdesk/data/recipes/*.json, the one recipe folder. Rewrites
    and coming-soon records are put there in dd_support (recipe_rewrite/add_to_catalog.py), and the
    catalog sync copies it to the server; nothing else is read."""
    src = catalog_dir() / "recipes"
    if not src.is_dir() or not any(src.glob("*.json")):
        raise RuntimeError(f"No recipe JSON files in {src}; configure DINNERDESK_CATALOG_DIR explicitly")
    records: dict[str, dict] = {}
    for path in sorted(src.glob("*.json")):
        data = json.loads(path.read_text())
        if not (data.get("slug") or data.get("id")):
            data = {**data, "slug": path.stem}
        records[str(data.get("id") or data.get("slug"))] = data
    # Files should already be normalized (scripts/normalize_catalog.py); this catches any that aren't.
    return [RecipeNormalizer.normalize(r)[0] for r in records.values()]


def import_recipes(conn, aliases: dict[str, str], report: dict | None = None) -> int:
    report = report if report is not None else {}
    photos = catalog_photos()
    n = 0
    soon: set[str] = set()
    for data in catalog_records():
        data = with_photo(data, photos)
        if Offering.withheld(str(data.get("name") or ""), data.get("tags")):
            continue
        if not ready(data, photos) and is_coming_soon(data, photos):
            data = coming_soon_record(data)
            soon.add(str(data.get("slug") or data.get("id")))
        elif data.get("coming_soon"):
            continue  # an original without our photo: nothing to show
        if not ready(data, photos) and not data.get("coming_soon") and not conn.execute(
            "SELECT 1 FROM recipes WHERE household_id IS NULL AND slug = ?",
            (str(data.get("slug") or data.get("id")),),
        ).fetchone():
            continue
        result = upsert_catalog_recipe(conn, data, aliases, report)
        report[result] = report.get(result, 0) + 1
        if result == "insert":
            n += 1
    # A coming-soon recipe that lost its photo, or whose file is gone, stops showing.
    for row in conn.execute(
        "SELECT id, slug FROM recipes WHERE household_id IS NULL AND provenance_json LIKE ?",
        (COMING_SOON_MARK,),
    ).fetchall():
        if row["slug"] not in soon:
            conn.execute("UPDATE recipes SET photo_path = '' WHERE id = ?", (row["id"],))
    report["coming_soon"] = len(soon)
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


def load_catalog(conn, report: dict | None = None) -> int:
    report = report if report is not None else {}
    seed_household(conn)
    n = import_recipes(conn, load_aliases(), report)
    for row in remove_withheld(conn):
        report.setdefault("withheld_kept", []).append({"id": row["id"], "slug": row["slug"], "name": row["name"]})
        print(f"kept withheld recipe {row['id']} {row['slug']} ({row['name']}): still in use")
    for row in remove_unready(conn):
        report.setdefault("unready_kept", []).append({"id": row["id"], "slug": row["slug"], "name": row["name"]})
        print(f"kept unready recipe {row['id']} {row['slug']} ({row['name']}): still in use")
    for c in report.get("conflicts") or []:
        print(f"kept admin edit of {c['slug']} ({c['part']}: {', '.join(c['fields'])}); the file differs")
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
